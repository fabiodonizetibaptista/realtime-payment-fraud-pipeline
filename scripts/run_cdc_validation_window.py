"""Janela integrada CDC: baseline -> conector -> c/u/d -> Avro -> teardown.

--check   : somente verificacoes locais, sem mutacoes remotas.
--execute : executa a janela integrada, incluindo teardown em finally.

Nao imprime credenciais, payloads ou saidas brutas de providers.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import base64
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
sys.path.insert(0, str(ROOT))

from safety import load_env_file

CONNECTOR_ADDRESS = "confluent_connector.payments_cdc[0]"
BASELINE = ROOT / ".local" / "stage5-cdc-baseline.json"
SCENARIO = ROOT / ".local" / "stage5-scenario.json"


def run_script(script, *args, timeout=240):
    result = subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env={**os.environ, "TF_LOG": "OFF"},
    )

    # Os scripts chamados produzem apenas indicadores sanitizados.
    # Nao repassar stdout/stderr integralmente ao terminal.
    for line in result.stdout.splitlines():
        if line.startswith((
            "PLAN_GATE=", "APPLY_GATE=", "BASELINE_GATE=",
            "SCENARIO_GATE=", "LIFECYCLE_GATE=",
            "VALIDATED_EVENT=", "TEARDOWN_GATE=",
            "CONNECTOR_ABSENT_FROM_STATE=",
        )):
            print(line, flush=True)

    return result.returncode == 0


def get_state():
    result = subprocess.run(
        ["terraform", "state", "pull"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )
    if result.returncode:
        raise RuntimeError("TERRAFORM_STATE_UNAVAILABLE")
    return json.loads(result.stdout)


def instances(state, resource_type, resource_name=None):
    for resource in state.get("resources", []):
        if resource.get("type") != resource_type:
            continue
        if resource_name and resource.get("name") != resource_name:
            continue
        for instance in resource.get("instances", []):
            yield instance.get("attributes") or {}


def connector_running():
    state = get_state()

    connector = list(instances(
        state, "confluent_connector", "payments_cdc"
    ))
    environment = list(instances(
        state, "confluent_environment"
    ))
    cluster = list(instances(
        state, "confluent_kafka_cluster"
    ))

    if not (
        len(connector) == 1
        and len(environment) == 1
        and len(cluster) == 1
    ):
        raise RuntimeError("CONNECTOR_RESOURCES_UNAVAILABLE")

    config = load_env_file(ROOT / ".env")
    key = os.environ.get("CONFLUENT_CLOUD_API_KEY") or config.get(
        "CONFLUENT_CLOUD_API_KEY"
    )
    secret = os.environ.get("CONFLUENT_CLOUD_API_SECRET") or config.get(
        "CONFLUENT_CLOUD_API_SECRET"
    )

    if not key or not secret:
        raise RuntimeError("CLOUD_AUTH_UNAVAILABLE")

    env_id = environment[0]["id"]
    cluster_id = cluster[0]["id"]
    name = connector[0].get("config_nonsensitive", {}).get(
        "name", "payments-cdc-aiven"
    )

    url = (
        "https://api.confluent.cloud/connect/v1/"
        f"environments/{quote(env_id)}/"
        f"clusters/{quote(cluster_id)}/"
        f"connectors/{quote(name)}/status"
    )

    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = json.load(response)
    except (urllib.error.URLError, ValueError):
        return False

    connector_state = (status.get("connector") or {}).get("state")
    tasks = status.get("tasks") or []

    if connector_state == "FAILED" or any(
        task.get("state") == "FAILED" for task in tasks
    ):
        raise RuntimeError("CONNECTOR_OR_TASK_FAILED")

    return (
        connector_state == "RUNNING"
        and bool(tasks)
        and all(task.get("state") == "RUNNING" for task in tasks)
    )


def check():
    print("========== ETAPA 5 — WINDOW PREFLIGHT ==========")

    required = (
        "scripts/plan_cdc_connector.py",
        "scripts/apply_cdc_connector.py",
        "scripts/teardown_cdc_connector.py",
        "scripts/cdc_test_scenario.py",
        "src/consumer/verify_cdc_lifecycle.py",
        "src/consumer/validate_cdc_avro.py",
        "infra/terraform/cdc-connector.tf",
        ".local/aiven-ca.pem",
        ".env",
    )

    missing = [
        item for item in required
        if not (ROOT / item).is_file()
    ]

    config = load_env_file(ROOT / ".env")
    credentials_ready = bool(config.get("CDC_PGPASSWORD"))

    print("REQUIRED_FILES_PRESENT=", not missing)
    print("CDC_CREDENTIAL_AVAILABLE=", credentials_ready)
    print("BASELINE_ALREADY_EXISTS=", BASELINE.exists())
    print("SCENARIO_ALREADY_EXISTS=", SCENARIO.exists())
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")

    ready = (
        not missing
        and credentials_ready
        and not BASELINE.exists()
        and not SCENARIO.exists()
    )

    print("WINDOW_PREPARATION_GATE=", "PASS" if ready else "BLOCKED")
    return ready


def execute():
    if not check():
        return 1

    print("========== ETAPA 5 — JANELA INTEGRADA ==========", flush=True)

    apply_attempted = False
    succeeded = False
    teardown_ok = False

    try:
        # O baseline precisa anteceder a producao dos eventos de teste.
        if not run_script(
            "src/consumer/verify_cdc_lifecycle.py", "--baseline"
        ):
            raise RuntimeError("BASELINE_FAILED")

        if not run_script("scripts/plan_cdc_connector.py"):
            raise RuntimeError("CONNECTOR_PLAN_FAILED")

        apply_attempted = True

        if not run_script("scripts/apply_cdc_connector.py", timeout=360):
            raise RuntimeError("CONNECTOR_APPLY_FAILED")

        print("WAITING_FOR_CONNECTOR_RUNNING=True", flush=True)

        deadline = time.monotonic() + 120

        while not connector_running():
            if time.monotonic() >= deadline:
                raise RuntimeError("CONNECTOR_RUNNING_TIMEOUT")
            time.sleep(10)

        print("CONNECTOR_RUNNING_GATE=PASS", flush=True)

        if not run_script(
            "scripts/cdc_test_scenario.py", "--execute"
        ):
            raise RuntimeError("SCENARIO_EXECUTION_FAILED")

        if not run_script(
            "src/consumer/verify_cdc_lifecycle.py",
            "--verify",
            timeout=160,
        ):
            raise RuntimeError("CDC_LIFECYCLE_VERIFICATION_FAILED")

        succeeded = True

    except Exception as error:
        print("WINDOW_ERROR_TYPE=", type(error).__name__, flush=True)
        if isinstance(error, RuntimeError):
            print("WINDOW_ERROR_CODE=", str(error), flush=True)

    finally:
        # Sempre tenta desligar caso o apply tenha sido iniciado,
        # inclusive quando a verificacao do CDC falhar.
        if apply_attempted:
            print("TEARDOWN_STARTED=True", flush=True)
            try:
                teardown_ok = run_script(
                    "scripts/teardown_cdc_connector.py",
                    "--execute",
                    timeout=360,
                )
            except Exception:
                teardown_ok = False

            print("TEARDOWN_SUCCESS=", teardown_ok, flush=True)
        else:
            print("CONNECTOR_APPLY_NOT_ATTEMPTED=True", flush=True)
            teardown_ok = True

        # Planos salvos podem conter credenciais.
        for name in ("cdc-stage4.tfplan", "cdc-teardown.tfplan"):
            (TF_DIR / name).unlink(missing_ok=True)

    complete = succeeded and teardown_ok
    print("WINDOW_GATE=", "PASS" if complete else "BLOCKED", flush=True)

    if not teardown_ok:
        print("URGENT_MANUAL_TEARDOWN_REQUIRED=True", flush=True)

    return 0 if complete else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    try:
        raise SystemExit(0 if check() else 1) if args.check else (
            sys.exit(execute())
        )
    except KeyboardInterrupt:
        print("WINDOW_INTERRUPTED=True", flush=True)
        print("VERIFY_CONNECTOR_TEARDOWN_REQUIRED=True", flush=True)
        raise SystemExit(130)
    except Exception as error:
        print("WINDOW_ERROR_TYPE=", type(error).__name__)
        print("WINDOW_GATE=BLOCKED")
        raise SystemExit(1)
