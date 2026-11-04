"""Aplica exclusivamente o plano aprovado de criacao do conector CDC."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "cdc-stage4.tfplan"
ADDRESS = "confluent_connector.payments_cdc[0]"


def terraform(*args):
    return subprocess.run(
        ["terraform", *args],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TF_LOG": "OFF"},
    )


def main():
    print("========== ETAPA 4 — ATIVIDADE 3: APPLY ==========")

    if not PLAN.is_file():
        print("APPLY_GATE=BLOCKED")
        print("REASON=APPROVED_PLAN_MISSING")
        return 1

    inspection = terraform("show", "-json", PLAN.name)

    if inspection.returncode != 0:
        print("APPLY_GATE=BLOCKED")
        print("REASON=PLAN_INSPECTION_FAILED")
        return 1

    data = json.loads(inspection.stdout)

    changes = [
        (
            item.get("address"),
            item.get("change", {}).get("actions"),
        )
        for item in data.get("resource_changes", [])
        if item.get("change", {}).get("actions")
        not in (["no-op"], ["read"])
    ]

    allowed = changes == [(ADDRESS, ["create"])]

    print("PLANNED_CHANGES=", len(changes))
    print("ONLY_CONNECTOR_CREATE=", allowed)
    print("FOUNDATION_MUTATIONS=", sum(
        1 for address, _ in changes if address != ADDRESS
    ))

    if not allowed:
        print("APPLY_GATE=BLOCKED")
        return 1

    # O plano salvo ja contem as variaveis aprovadas.
    # Nao imprime output bruto: providers podem incluir dados sensiveis.
    result = terraform(
        "apply",
        "-input=false",
        "-no-color",
        PLAN.name,
    )

    print("TERRAFORM_APPLY_SUCCESS=", result.returncode == 0)

    state = terraform("state", "list")
    present = (
        state.returncode == 0
        and ADDRESS in state.stdout.splitlines()
    )

    print("CONNECTOR_IN_STATE=", present)
    print("SECRETS_PRINTED=False")

    if result.returncode != 0:
        print("ERROR_CATEGORY=CONNECTOR_PROVISIONING_FAILED")
        print("ERROR_DETAILS_REDACTED=True")
        print("APPLY_GATE=BLOCKED")
        return 1

    # Evidencia dedicada, sem stdout/stderr do provider ou credenciais.
    from datetime import datetime, timezone

    evidence_dir = ROOT / "evidencias" / "v2"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "resource": ADDRESS,
        "planned_changes": len(changes),
        "only_connector_create": allowed,
        "terraform_apply_success": result.returncode == 0,
        "connector_in_state": present,
        "gate": "PASS" if present else "BLOCKED",
        "secret_values_recorded": False,
    }
    (evidence_dir / f"{timestamp}-stage4-terraform-apply.json").write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )
    print("APPLY_EVIDENCE_SAVED=True")

    print("APPLY_GATE=", "PASS" if present else "BLOCKED")
    return 0 if present else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("APPLY_GATE=BLOCKED")
        raise SystemExit(1)
