"""Execucao controlada da Etapa 11 no Confluent Flink.

Comandos:
  plan          Valida arquivos localmente, sem acessar a nuvem.
  start         Inicia o processamento continuo (acao cloud explicita).
  status        Consulta o estado do statement.
  inspect       Consulta resultados de correspondencias.
  inspect-null  Consulta registros de origem sem cartao.

Nunca imprime credenciais, Terraform State ou linhas brutas de dados.
"""

import argparse
from dataclasses import replace
from pathlib import Path

from scripts.flink_portability import render_for_runtime, resolve_names
from scripts.flink_runtime import FlinkRuntime, FlinkRuntimeError

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql" / "fraud_detection" / "continuous"

FILES = {
    "start": "01_continuous_matches.sql",
    "inspect": "02_inspect_matches.sql",
    "inspect-null": "03_inspect_null_cards.sql",
}

STATEMENT_NAME = "etapa11-fraud-pattern-matches"
MANIFEST = ROOT / ".local" / "etapa12-scenarios.json"

# Consulta dirigida ao cenario sintetico. Os IDs vem do manifesto local
# (inteiros negativos gerados por fraud_scenarios) e sao convertidos com
# int() antes da interpolacao; nenhum texto externo entra no SQL.
VERIFY_SQL = """
SELECT first_transaction_id, middle_transaction_id, last_transaction_id,
       transaction_count
FROM `desafio-final`.`desafio-basic`.`fraud.pattern_matches`
WHERE first_transaction_id IN ({ids})
   OR middle_transaction_id IN ({ids})
   OR last_transaction_id IN ({ids})
LIMIT 50
"""


def load_sql(action):
    """Carrega somente SQL versionada e esperada para esta etapa."""
    sql = (SQL_DIR / FILES[action]).read_text(encoding="utf-8")
    if not sql.strip():
        raise ValueError("SQL_EMPTY")
    return sql


def build_runtime():
    """Usa metadados do Terraform sem exibir o State."""
    runtime = FlinkRuntime.from_terraform_state()
    catalog, database = resolve_names(runtime.config)
    runtime.config = replace(
        runtime.config,
        catalog_name=catalog,
        database_name=database,
    )
    return runtime


def statement_status(runtime):
    """Consulta o statement sem modificar seu ciclo de vida."""
    statement = runtime.find_statement(STATEMENT_NAME)
    if statement is None:
        return "NOT_FOUND"
    return runtime.statement_phase(statement) or "UNKNOWN"


def start(runtime):
    """Inicia somente quando nao existe um statement com esse nome."""
    phase = statement_status(runtime)

    if phase == "RUNNING":
        print("PROCESSAMENTO_JA_ATIVO=True")
        return

    if phase != "NOT_FOUND":
        raise FlinkRuntimeError(
            "STATEMENT_EXISTS_REQUIRES_MANUAL_REVIEW"
        )

    sql = render_for_runtime(load_sql("start"), runtime)

    # Uma consulta continua nao deve aguardar COMPLETED.
    runtime.create_statement(
        STATEMENT_NAME,
        sql,
        wait=False,
    )

    phase = statement_status(runtime)
    print(f"STATEMENT_PHASE={phase}")

    if phase == "RUNNING":
        print("PROCESSAMENTO_CONTINUO_ATIVO=True")
    elif phase in {"FAILED", "COMPLETED", "CANCELLED", "STOPPED"}:
        raise FlinkRuntimeError("CONTINUOUS_STATEMENT_NOT_RUNNING")
    else:
        # A submissao pode terminar antes do statement entrar em RUNNING.
        # Confirmar o estado posteriormente com o comando status.
        print("START_SUBMITTED=True")
        print("RUNNING_CONFIRMATION_PENDING=True")


def inspect(runtime, action):
    """Executa SELECT separado, com limite fixo de registros."""
    sql = render_for_runtime(load_sql(action), runtime)
    rows = runtime.query(sql, timeout=35)

    # Nunca imprimir automaticamente IDs, valores ou dados de clientes.
    print(f"INSPECTION_TYPE={action}")
    print(f"ROWS_OBSERVED={len(rows)}")

    if action == "inspect":
        print(
            "HAS_CARD_ID_FIELD="
            + str(any("card_id" in row for row in rows))
        )
        print(
            "HAS_TIME_FIELDS="
            + str(any(
                "first_rowtime" in row and "last_rowtime" in row
                for row in rows
            ))
        )


def load_manifest(path=None):
    """IDs sinteticos do cenario: [legitimo, fraude_1, fraude_2, fraude_3]."""
    import json

    path = path or MANIFEST
    if not path.is_file():
        raise FlinkRuntimeError("SCENARIO_MANIFEST_MISSING")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    ids = [int(value) for value in manifest.get("test_ids", [])]
    if manifest.get("status") != "COMPLETED" or len(ids) != 4 or len(set(ids)) != 4:
        raise FlinkRuntimeError("SCENARIO_MANIFEST_INCOMPLETE")
    return ids


def evaluate_scenario(rows, ids):
    """PASS somente se a fraude casar exatamente e o legitimo nao casar."""
    legitimate, fraud = ids[0], tuple(ids[1:])
    triples = []
    for row in rows:
        try:
            triples.append(tuple(int(row[key]) for key in (
                "first_transaction_id", "middle_transaction_id", "last_transaction_id",
            )))
        except (KeyError, TypeError, ValueError):
            continue
    fraud_match = fraud in triples
    legitimate_matched = any(legitimate in triple for triple in triples)
    return {
        "FRAUD_SEQUENCE_MATCHED": fraud_match,
        "FRAUD_MATCHES_FOR_SCENARIO": sum(1 for t in triples if set(t) & set(fraud)),
        "LEGITIMATE_IN_ANY_MATCH": legitimate_matched,
        "SCENARIO_ALERT_GATE": "PASS" if fraud_match and not legitimate_matched else "PENDING_OR_FAIL",
    }


def verify_scenario(runtime, save=True):
    """Consulta somente matches que contenham IDs do cenario; imprime booleanos."""
    ids = load_manifest()
    sql = VERIFY_SQL.format(ids=", ".join(str(int(value)) for value in ids))
    rows = runtime.query(render_for_runtime(sql, runtime), timeout=35)
    result = evaluate_scenario(rows, ids)
    print("INSPECTION_TYPE=verify-scenario")
    for key, value in result.items():
        print(f"{key}={value}")
    print("TRANSACTION_IDS_PRINTED=False")
    if save:
        save_scenario_evidence(result)
    return result


def save_scenario_evidence(result, path=None):
    """Grava somente booleanos/contagens; nenhum ID ou valor de transacao."""
    import json
    import sys
    from datetime import datetime, timezone

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from safety import evidence_path

    path = path or evidence_path(ROOT, "flink/fraud-scenario-alert.json")
    if path.exists():
        print("EVIDENCE_SAVED=False; EVIDENCE_ALREADY_EXISTS")
        return path
    record = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "statement": STATEMENT_NAME,
        "pattern": "3 transacoes do mesmo cartao em ate 60 s (MATCH_RECOGNIZE)",
        **{key.lower(): value for key, value in result.items()},
        "transaction_ids_recorded": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("EVIDENCE_SAVED=True")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Executor controlado da Etapa 11"
    )
    parser.add_argument(
        "action",
        choices=("plan", "start", "status", "inspect", "inspect-null", "verify-scenario"),
    )
    parser.add_argument(
        "--confirm-start",
        action="store_true",
        help="Autoriza criar o statement continuo no ambiente cloud",
    )
    args = parser.parse_args()

    if args.action == "plan":
        for action in FILES:
            sql = load_sql(action)
            print(f"SQL_{action.upper().replace('-', '_')}=READY")
            print(f"SQL_BYTES_{action.upper().replace('-', '_')}={len(sql.encode('utf-8'))}")
        print("CLOUD_EXECUTION=False")
        return

    if args.confirm_start and args.action != "start":
        parser.error("--confirm-start so pode ser usado com start")

    if args.action == "start" and not args.confirm_start:
        parser.error("start exige --confirm-start")

    runtime = build_runtime()

    if args.action == "start":
        start(runtime)
    elif args.action == "status":
        phase = statement_status(runtime)
        print(f"STATEMENT_PHASE={phase}")
        if phase != "RUNNING":
            # Codigo de saida != 0 para o roteiro parar (&&) se nao estiver rodando.
            raise SystemExit(1)
    elif args.action == "verify-scenario":
        verify_scenario(runtime)
    else:
        inspect(runtime, args.action)


if __name__ == "__main__":
    try:
        main()
    except (FlinkRuntimeError, ValueError, OSError) as exc:
        # Apenas codigos de erro controlados; nao exibir saidas da CLI.
        print(f"ETAPA11_ERROR={type(exc).__name__}")
        raise SystemExit(1) from None
