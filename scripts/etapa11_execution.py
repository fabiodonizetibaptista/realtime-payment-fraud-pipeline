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
SQL_DIR = ROOT / "sql" / "etapa-11"

FILES = {
    "start": "01_continuous_matches.sql",
    "inspect": "02_inspect_matches.sql",
    "inspect-null": "03_inspect_null_cards.sql",
}

STATEMENT_NAME = "etapa11-fraud-pattern-matches"


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


def main():
    parser = argparse.ArgumentParser(
        description="Executor controlado da Etapa 11"
    )
    parser.add_argument(
        "action",
        choices=("plan", "start", "status", "inspect", "inspect-null"),
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
        print(f"STATEMENT_PHASE={statement_status(runtime)}")
    else:
        inspect(runtime, args.action)


if __name__ == "__main__":
    try:
        main()
    except (FlinkRuntimeError, ValueError, OSError) as exc:
        # Apenas codigos de erro controlados; nao exibir saidas da CLI.
        print(f"ETAPA11_ERROR={type(exc).__name__}")
        raise SystemExit(1) from None
