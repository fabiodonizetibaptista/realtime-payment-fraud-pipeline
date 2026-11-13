"""Onde estou e como retomar? (`python lab.py status`, somente leitura).

Para quem perdeu o terminal no meio do roteiro (queda de internet, Codespace
reiniciado, computador travado). A situacao e deduzida do que existe de fato —
Terraform State, .env gerado, evidencias da execucao — e nao de um registro
que poderia estar desatualizado. Mostra:

- quais blocos do roteiro ja foram concluidos e qual e o proximo;
- o que esta cobrando agora (conector, statements Flink rodando);
- as linhas `export` para restaurar a sessao do terminal;
- travas e restos que exigem atencao.

Nunca imprime valores do .env nem do State, apenas nomes, IDs e contagens.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import load_env_file, saved_run_id  # noqa: E402

TF_DIR = ROOT / "infra" / "terraform"
POSTGRES = "aiven_pg.payments"
POOL = "confluent_flink_compute_pool.payment_fraud"
CONNECTOR = "confluent_connector.payments_cdc[0]"
SUBJECT = "confluent_subject_config.transactions_value[0]"
CDC_ACL = "confluent_kafka_acl.cdc_topic_write[0]"


@dataclass
class Snapshot:
    """Tudo o que o status precisa, coletado uma vez (facil de simular em teste)."""
    state: set = field(default_factory=set)
    state_available: bool = True
    env_keys: set = field(default_factory=set)
    run_id: str = ""
    evidence: set = field(default_factory=set)   # caminhos relativos a evidencias/runs/<id>/
    connector_created_at: str = ""               # da evidencia do apply do conector
    running_statements: int | None = None        # None = nao verificado
    state_lock: bool = False
    leftover_plans: list = field(default_factory=list)


def has_evidence(snapshot, prefix):
    return any(path.startswith(prefix) for path in snapshot.evidence)


def blocks(snapshot, foundation):
    """Lista ordenada (bloco, concluido?, descricao)."""
    state, keys = snapshot.state, snapshot.env_keys
    j4_done = has_evidence(snapshot, "observability/metrics-api-")
    return [
        ("J1.1", foundation <= state, "fundacao (14 recursos)"),
        ("J1.2", "TF_VAR_foundation_kafka_api_key" in keys, "variaveis geradas no .env"),
        ("J1.3", {POSTGRES, POOL} <= state, "pipeline (Postgres, pool Flink, identidades)"),
        ("J2", {"PGHOST", "CDC_PGPASSWORD"} <= keys, "origem PostgreSQL e usuario CDC"),
        ("J3", CDC_ACL in state, "ACLs"),
        ("J4.1", has_evidence(snapshot, "cdc/stage5-cdc-lifecycle"), "conector e ciclo CDC"),
        ("J4.2", has_evidence(snapshot, "schemas/stage6-compatibility-summary"), "contrato Avro"),
        ("J4.3", has_evidence(snapshot, "flink/fraud-scenario-alert"), "Flink e alerta"),
        ("J4.4", j4_done, "metricas e inventario"),
        ("J5", j4_done and CONNECTOR not in state, "conector removido"),
    ]


def assess(snapshot, foundation):
    """Situacao geral, proximo bloco e cobrancas ativas."""
    managed = {a for a in snapshot.state if not a.startswith("data.")}
    if not snapshot.state_available:
        return {"situation": "SEM_STATE_INICIALIZADO", "next": "J0.1", "billing": []}

    billing = []
    if CONNECTOR in managed:
        since = f" desde {snapshot.connector_created_at}" if snapshot.connector_created_at else ""
        billing.append(f"conector CDC ativo{since} (cobra por hora de task)")
    if snapshot.running_statements:
        billing.append(f"{snapshot.running_statements} statement(s) Flink rodando (cobra CFU)")
    if foundation & managed:
        billing.append("cluster Kafka Basic (cobra por hora enquanto existir)")

    if not managed:
        done_before = bool(snapshot.evidence)
        return {
            "situation": "TUDO_DERRUBADO" if done_before else "NADA_PROVISIONADO",
            "next": "J7 (custo)" if done_before else "J0.2",
            "billing": [],
        }

    steps = blocks(snapshot, foundation)
    pending = next((name for name, done, _ in steps if not done), None)
    return {
        "situation": "EM_ANDAMENTO",
        "next": pending or "J6 (teardown total)",
        "billing": billing,
        "steps": steps,
    }


def window_start(created_at):
    """WINDOW_START (minuto UTC) a partir do horario do apply do conector."""
    try:
        moment = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")


def render(snapshot, foundation, outputs):
    result = assess(snapshot, foundation)
    lines = ["=== STATUS DA EXECUCAO ==="]
    lines.append(f"SITUACAO={result['situation']}")
    for name, done, text in result.get("steps", []):
        lines.append(f"  [{'x' if done else ' '}] {name:5} {text}")
    lines.append(f"PROXIMO_BLOCO={result['next']}")

    if result["billing"]:
        lines.append("COBRANDO_AGORA:")
        lines.extend(f"  - {item}" for item in result["billing"])
        lines.append("  Se nao for continuar agora: va ao J5 e ao J6 do roteiro para parar a cobranca.")
    if snapshot.running_statements is None and POOL in snapshot.state:
        lines.append("STATEMENTS_FLINK=NAO_VERIFICADO (rode confluent login --no-browser e repita)")

    exports = []
    if snapshot.run_id:
        exports.append(f"export EVIDENCE_RUN_ID={snapshot.run_id}")
    for name, value in (("ENV_ID", outputs.get("environment_id")), ("KAFKA_ID", outputs.get("kafka_cluster_id"))):
        if value:
            exports.append(f"export {name}={value}")
    if snapshot.connector_created_at:
        start = window_start(snapshot.connector_created_at)
        if start:
            exports.append(f"export WINDOW_START={start}")
    if exports:
        lines.append("RESTAURAR_SESSAO (cole no terminal):")
        lines.extend(f"  {line}" for line in exports)

    if snapshot.state_lock:
        lines.append("ALERTA=STATE_TRAVADO: infra/terraform/.terraform.tfstate.lock.info existe. "
                     "Se nenhum terraform estiver rodando (ps aux | grep terraform), "
                     "a operacao anterior foi interrompida: rode o bloco de novo; se o "
                     "Terraform recusar pela trava, use terraform -chdir=infra/terraform force-unlock <ID>.")
    if snapshot.leftover_plans:
        lines.append("INFO=planos de tentativa anterior (" + ", ".join(snapshot.leftover_plans)
                     + ") serao descartados automaticamente no proximo plano.")
    return lines


# ---- coleta real (somente leitura) ----

def _run(args, cwd=ROOT, timeout=60):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect():
    snapshot = Snapshot()
    result = _run(["terraform", "state", "list"], cwd=TF_DIR)
    if result is None or result.returncode != 0:
        snapshot.state_available = (TF_DIR / ".terraform").is_dir()
    else:
        snapshot.state = {line for line in result.stdout.splitlines() if line}
    env_file = ROOT / ".env"
    snapshot.env_keys = {k for k, v in load_env_file(env_file).items() if v} if env_file.is_file() else set()
    import os
    snapshot.run_id = os.environ.get("EVIDENCE_RUN_ID", "").strip() or saved_run_id(ROOT)
    if snapshot.run_id:
        base = ROOT / "evidencias" / "runs" / snapshot.run_id
        if base.is_dir():
            snapshot.evidence = {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}
            applies = sorted(base.glob("cdc/*-stage4-terraform-apply.json"))
            if applies:
                try:
                    snapshot.connector_created_at = json.loads(
                        applies[-1].read_text(encoding="utf-8")).get("captured_at_utc", "")
                except (OSError, ValueError):
                    pass
    snapshot.state_lock = (TF_DIR / ".terraform.tfstate.lock.info").exists()
    snapshot.leftover_plans = sorted(p.name for p in TF_DIR.glob("*.tfplan"))
    if POOL in snapshot.state:
        try:
            from scripts.flink_runtime import FlinkRuntime
            statements = FlinkRuntime.from_terraform_state().list_statements()
            snapshot.running_statements = sum(
                1 for s in statements if FlinkRuntime.statement_phase(s) in {"RUNNING", "PENDING", "PROVISIONING"})
        except Exception:
            snapshot.running_statements = None
    return snapshot


def terraform_outputs():
    values = {}
    for name in ("environment_id", "kafka_cluster_id"):
        result = _run(["terraform", "output", "-raw", name], cwd=TF_DIR, timeout=30)
        if result is not None and result.returncode == 0 and result.stdout.strip() and "\n" not in result.stdout.strip():
            values[name] = result.stdout.strip()
    return values


def main(foundation):
    snapshot = collect()
    outputs = terraform_outputs() if snapshot.state else {}
    for line in render(snapshot, foundation, outputs):
        print(line)
    return 0
