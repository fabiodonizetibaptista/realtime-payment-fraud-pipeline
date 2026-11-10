"""Verifica o CDC da Etapa 4 e desliga o conector ao final."""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra" / "terraform"
sys.path.insert(0, str(ROOT))

from safety import load_env_file


def execute(command, cwd=ROOT):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TF_LOG": "OFF"},
    )


def basic_auth(key, secret):
    encoded = base64.b64encode(
        f"{key}:{secret}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


def get_json(url, key, secret):
    request = urllib.request.Request(
        url,
        headers={
            **basic_auth(key, secret),
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None
    except Exception:
        return 0, None


def resource(state, kind, name=None):
    for item in state.get("resources", []):
        if item.get("type") != kind:
            continue
        if name is not None and item.get("name") != name:
            continue
        for instance in item.get("instances", []):
            yield item["name"], instance.get("attributes") or {}


def main():
    print("========== ETAPA 4 — CDC OPERACIONAL ==========", flush=True)

    config = load_env_file(ROOT / ".env")
    cloud_key = os.environ.get("CONFLUENT_CLOUD_API_KEY") or config.get(
        "CONFLUENT_CLOUD_API_KEY"
    )
    cloud_secret = os.environ.get("CONFLUENT_CLOUD_API_SECRET") or config.get(
        "CONFLUENT_CLOUD_API_SECRET"
    )

    if not cloud_key or not cloud_secret:
        print("CLOUD_AUTH_AVAILABLE=False", flush=True)
        return 1

    pulled = execute(["terraform", "state", "pull"], cwd=TF)

    if pulled.returncode != 0:
        print("STATE_READ=BLOCKED", flush=True)
        return 1

    state = json.loads(pulled.stdout)

    connectors = list(resource(state, "confluent_connector", "payments_cdc"))
    environments = list(resource(state, "confluent_environment"))
    clusters = list(resource(state, "confluent_kafka_cluster"))

    if len(connectors) != 1 or len(environments) != 1 or len(clusters) != 1:
        print("RESOURCE_IDENTIFICATION=BLOCKED", flush=True)
        return 1

    connector = connectors[0][1]
    environment_id = environments[0][1]["id"]
    cluster = clusters[0][1]
    cluster_id = cluster["id"]
    rest_endpoint = cluster.get("rest_endpoint", "").rstrip("/")

    connector_name = connector.get("config_nonsensitive", {}).get(
        "name", "payments-cdc-aiven"
    )

    status_url = (
        "https://api.confluent.cloud/connect/v1/"
        f"environments/{quote(environment_id)}/"
        f"clusters/{quote(cluster_id)}/"
        f"connectors/{quote(connector_name)}/status"
    )

    # Encontra a chave de administracao Kafka no State.
    # Os valores sao usados exclusivamente em memoria.
    admin_keys = [
        attrs
        for name, attrs in resource(state, "confluent_api_key")
        if "admin" in name.lower()
        and attrs.get("id")
        and attrs.get("secret")
    ]

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector_name": connector_name,
        "connector_state": "UNKNOWN",
        "task_states": [],
        "expected_topics": [
            "payments.public.customers",
            "payments.public.accounts",
            "payments.public.cards",
            "payments.public.merchants",
            "payments.public.transactions",
            "payments.cdc_internal.heartbeat",
        ],
        "observed_topics": [],
    }

    try:
        # Janela de verificacao limitada para controlar custos.
        deadline = time.monotonic() + 90

        while True:
            http_code, status = get_json(
                status_url, cloud_key, cloud_secret
            )

            print("CONNECTOR_STATUS_HTTP=", http_code, flush=True)

            if http_code != 200 or not isinstance(status, dict):
                print("CONNECTOR_STATUS_CHECK=BLOCKED", flush=True)
                break

            connector_data = status.get("connector") or {}
            report["connector_state"] = connector_data.get("state", "UNKNOWN")
            report["task_states"] = [
                item.get("state", "UNKNOWN")
                for item in status.get("tasks", [])
            ]

            running = (
                report["connector_state"] == "RUNNING"
                and bool(report["task_states"])
                and all(x == "RUNNING" for x in report["task_states"])
            )

            print(
                "CONNECTOR_RUNNING=", report["connector_state"] == "RUNNING",
                flush=True
            )
            print("ALL_TASKS_RUNNING=", running, flush=True)

            if running:
                break

            if report["connector_state"] == "FAILED":
                break

            if time.monotonic() >= deadline:
                break

            time.sleep(10)

        if admin_keys and rest_endpoint:
            key = admin_keys[0]
            url = (
                f"{rest_endpoint}/kafka/v3/"
                f"clusters/{quote(cluster_id)}/topics"
            )

            http_code, response = get_json(
                url, key["id"], key["secret"]
            )

            print("KAFKA_TOPICS_HTTP=", http_code, flush=True)

            if http_code == 200 and isinstance(response, dict):
                report["observed_topics"] = sorted(
                    item["topic_name"]
                    for item in response.get("data", [])
                    if isinstance(item.get("topic_name"), str)
                    and item["topic_name"].startswith("payments.")
                )
        else:
            print("KAFKA_ADMIN_CREDENTIAL_AVAILABLE=False", flush=True)

        expected = set(report["expected_topics"])
        observed = set(report["observed_topics"])

        print("CDC_TOPICS_FOUND=", len(expected & observed), flush=True)
        print("CDC_TOPICS_EXPECTED=", len(expected), flush=True)
        print("MISSING_TOPICS=", sorted(expected - observed), flush=True)

        report["operational_gate"] = (
            "PASS"
            if report["connector_state"] == "RUNNING"
            and bool(report["task_states"])
            and all(x == "RUNNING" for x in report["task_states"])
            and expected.issubset(observed)
            else "BLOCKED"
        )

        evidence_dir = ROOT / "evidencias" / "cdc"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = evidence_dir / "stage4-cdc-operational.json"
        evidence_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        print("EVIDENCE_SAVED=True", flush=True)
        print("OPERATIONAL_GATE=", report["operational_gate"], flush=True)

    finally:
        print("========== TEARDOWN AUTOMATICO ==========", flush=True)
        teardown = execute([
            sys.executable,
            str(ROOT / "scripts" / "teardown_cdc_connector.py"),
            "--execute",
        ])

        # O teardown imprime somente indicadores seguros.
        print(teardown.stdout, end="", flush=True)

        if teardown.returncode != 0:
            print("TEARDOWN_REQUIRES_ATTENTION=True", flush=True)
        else:
            print("TEARDOWN_SCRIPT_EXIT=PASS", flush=True)

    return 0 if (
        report.get("operational_gate") == "PASS"
        and teardown.returncode == 0
    ) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("INTERRUPTED: CHECK_TEARDOWN_STATUS", flush=True)
        raise SystemExit(130)
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__, flush=True)
        print("VERIFY_GATE=BLOCKED", flush=True)
        raise SystemExit(1)
