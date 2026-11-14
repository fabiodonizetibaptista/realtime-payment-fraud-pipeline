"""Valida a configuracao do conector CDC sem cria-lo (Connect API config/validate).

Motivo: quando o apply falha com CONNECTOR_PROVISIONING_FAILED, o conector
nao chega a existir, entao nao ha `connect cluster describe` possivel, e a
classificacao estruturada (connector_diagnostics) informa a categoria, mas
nao o campo rejeitado. Este script envia a MESMA configuracao do plano salvo
ao endpoint de validacao e imprime somente nome do campo e mensagem de erro.

Garantias:
- nao cria, altera ou remove recursos (endpoint de validacao; sem custo);
- nunca imprime valores de configuracao (a resposta ecoa valores; sao ignorados);
- mensagens que contenham qualquer valor sensivel sao omitidas.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import load_env_file  # noqa: E402
from scripts.connector_diagnostics import classify  # noqa: E402

TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "cdc-stage4.tfplan"
ADDRESS = "confluent_connector.payments_cdc[0]"
PLUGIN = "PostgresCdcSourceV2"
API = "https://api.confluent.cloud/connect/v1"
OMITTED = "<mensagem omitida: contem valor sensivel>"


def connector_from_plan(plan: dict) -> tuple[str, str, dict, dict]:
    for change in plan.get("resource_changes", []):
        if change.get("address") == ADDRESS:
            after = change["change"]["after"]
            return (
                after["environment"][0]["id"],
                after["kafka_cluster"][0]["id"],
                dict(after["config_nonsensitive"]),
                dict(after["config_sensitive"]),
            )
    raise RuntimeError("VALIDATE_BLOCKED=CONNECTOR_NOT_IN_PLAN")


def sensitive_fragments(values) -> list[str]:
    """Valores inteiros e cada linha longa (cobre PEM e segredos multilinha)."""
    fragments = set()
    for value in values:
        if not value:
            continue
        fragments.add(value)
        fragments.update(line.strip() for line in value.splitlines() if len(line.strip()) >= 12)
    return sorted(fragments, key=len, reverse=True)


def field_errors(response: dict, fragments: list[str]) -> list[tuple[str, str]]:
    """Somente (campo, mensagem); valores ecoados pela API nunca sao lidos."""
    found = []
    for item in response.get("configs", []):
        value = item.get("value", {})
        name = str(value.get("name", "?"))
        for message in value.get("errors", []) or []:
            message = str(message)
            if any(fragment in message for fragment in fragments):
                message = OMITTED
            found.append((name, message))
    return found


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    if not PLAN.is_file():
        print("VALIDATE_BLOCKED=PLAN_NOT_FOUND; execute scripts/plan_cdc_connector.py")
        return 1

    env = {**load_env_file(ROOT / ".env"), **{k: v for k, v in os.environ.items() if v}}
    key, secret = env.get("CONFLUENT_CLOUD_API_KEY"), env.get("CONFLUENT_CLOUD_API_SECRET")
    if not key or not secret:
        print("VALIDATE_BLOCKED=CLOUD_API_KEY_MISSING")
        return 1

    shown = subprocess.run(
        ["terraform", "show", "-json", PLAN.name], cwd=TF_DIR, capture_output=True,
        text=True, check=False, env={**os.environ, "TF_LOG": "OFF"},
    )
    if shown.returncode != 0:
        print("VALIDATE_BLOCKED=PLAN_READ_FAILED")
        return 1
    env_id, cluster_id, nonsensitive, sensitive = connector_from_plan(json.loads(shown.stdout))
    fragments = sensitive_fragments([*sensitive.values(), key, secret])

    request = urllib.request.Request(
        f"{API}/environments/{env_id}/clusters/{cluster_id}/connector-plugins/{PLUGIN}/config/validate",
        data=json.dumps({**nonsensitive, **sensitive}).encode(),
        method="PUT",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode(),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            response = json.load(reply)
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        print(f"VALIDATE_HTTP_STATUS={error.code}")
        print(f"VALIDATE_DIAGNOSTIC_CATEGORY={classify(body)['category']}")
        print("PROVIDER_TEXT_PRINTED=False")
        return 1
    except urllib.error.URLError:
        print("VALIDATE_BLOCKED=NETWORK")
        return 1

    errors = field_errors(response, fragments)
    print(f"VALIDATE_ERROR_COUNT={response.get('error_count', len(errors))}")
    for name, message in errors:
        print(f"FIELD={name} ERROR={message}")
    print("CONFIG_VALUES_PRINTED=False")
    print("REMOTE_CHANGES=False")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
