"""Reconcilia o Terraform State com a nuvem apos um teardown parcial (T2).

plan                 terraform plan -refresh-only; mostra so endereco e acao do drift
apply --confirm      aplica o refresh revisado (atualiza somente o State)

Motivo: `lab.py teardown` nao pode ser repetido as cegas. Quando ele falha no
meio, o State pode listar recursos que ja nao existem (ex.: ACLs de um cluster
que foi destruido). O refresh-only deixa o State igual ao remoto; depois, um
novo `lab.py teardown` planeja somente os remanescentes reais.

Nao cria nem destroi recursos remotos. Erros do provider sao mostrados apenas
mascarados na tela (nunca gravados). O plano e removido ao final.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import discard_stale_plan, load_env_file  # noqa: E402
from scripts.connector_diagnostics import SECRET_NAME, masked_error_lines  # noqa: E402

TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "refresh.tfplan"


def execution_env() -> dict:
    env = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.is_file():
        for key, value in load_env_file(env_file).items():
            if value and not env.get(key):
                env[key] = value
    env["TF_LOG"] = "OFF"
    env["TF_INPUT"] = "0"
    return env


def terraform(*args, env):
    return subprocess.run(["terraform", *args], cwd=TF_DIR, env=env,
                          capture_output=True, text=True, check=False)


def show_masked_error(result, env):
    secrets = [v for k, v in env.items() if v and SECRET_NAME.search(k)]
    print("===== ERRO DO PROVIDER (mascarado; nao gravado) =====")
    for line in masked_error_lines(result.stderr + "\n" + result.stdout, secrets) or ["<sem linha Error:>"]:
        print(line)
    print("===== FIM DO ERRO =====")


def drift(plan: dict) -> list[tuple[str, str]]:
    """Somente (acao, endereco) do drift detectado; nunca atributos."""
    items = []
    for item in plan.get("resource_drift", []) or []:
        actions = ",".join((item.get("change") or {}).get("actions") or [])
        items.append((actions, str(item.get("address"))))
    return sorted(items)


def plan_refresh(env) -> int:
    discard_stale_plan(PLAN)
    result = terraform("plan", "-refresh-only", "-no-color", "-input=false",
                       f"-out={PLAN.name}", env=env)
    if result.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("RECONCILE_PLAN=FAILED")
        show_masked_error(result, env)
        return 1
    shown = terraform("show", "-json", PLAN.name, env=env)
    if shown.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("RECONCILE_PLAN=SHOW_FAILED")
        return 1
    items = drift(json.loads(shown.stdout))
    print(f"DRIFT_COUNT={len(items)}")
    for actions, address in items:
        print(f"DRIFT {actions} {address}")
    print("RECONCILE_PLAN=READY; REMOTE_CHANGES=False")
    print("NEXT=python scripts/reconcile_state.py apply --confirm")
    return 0


def apply_refresh(env) -> int:
    if not PLAN.exists():
        print("RECONCILE_BLOCKED=PLAN_NOT_FOUND")
        return 1
    try:
        result = terraform("apply", "-no-color", "-input=false", PLAN.name, env=env)
        if result.returncode != 0:
            print("RECONCILE_APPLY=FAILED")
            show_masked_error(result, env)
            return 1
        state = terraform("state", "list", env=env)
        managed = [line for line in state.stdout.splitlines() if line and not line.startswith("data.")]
        print("RECONCILE_APPLY=OK; STATE_ONLY=True")
        print(f"MANAGED_IN_STATE={len(managed)}")
        for address in managed:
            print(f"IN_STATE {address}")
        return 0
    finally:
        PLAN.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("plan", "apply"))
    parser.add_argument("--confirm", action="store_true", help="exigido por apply")
    args = parser.parse_args()
    env = execution_env()
    if args.action == "plan":
        return plan_refresh(env)
    if not args.confirm:
        parser.error("apply exige --confirm")
    return apply_refresh(env)


if __name__ == "__main__":
    raise SystemExit(main())
