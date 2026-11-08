"""Idempotent preparation of the Flink source tables."""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from scripts.flink_runtime import (
    FlinkRuntime,
    FlinkRuntimeError,
)


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DDLStep:
    name: str
    table: str
    inspect_file: str
    ddl_file: str
    kind: str
    expected: str


STEPS = (
    DDLStep(
        name="payment-fraud-setup-accounts-pk",
        table="accounts",
        inspect_file="sql/etapa-9/07_show_create_accounts.sql",
        ddl_file="sql/stage8_accounts_primary_key.sql",
        kind="primary_key",
        expected="account_id",
    ),
    DDLStep(
        name="payment-fraud-setup-transactions-pk",
        table="transactions",
        inspect_file="sql/etapa-9/06_show_create_transactions.sql",
        ddl_file="sql/etapa-9/08_add_transactions_primary_key.sql",
        kind="primary_key",
        expected="transaction_id",
    ),
    DDLStep(
        name="payment-fraud-setup-transactions-append",
        table="transactions",
        inspect_file="sql/etapa-9/06_show_create_transactions.sql",
        ddl_file="sql/etapa-9/09_set_transactions_append.sql",
        kind="changelog",
        expected="append",
    ),
)


def load_sql(path):
    """Read SQL without modifying its versioned source file."""
    path = ROOT / path

    if not path.is_file():
        raise FlinkRuntimeError("SQL_SOURCE_FILE_MISSING")

    raw = path.read_text(encoding="utf-8-sig")

    # Remove full-line SQL comments.
    lines = [
        line for line in raw.splitlines()
        if not line.strip().startswith("--")
    ]

    statements = [
        item.strip()
        for item in "\n".join(lines).split(";")
        if item.strip()
    ]

    if not statements:
        raise FlinkRuntimeError("SQL_SOURCE_FILE_EMPTY")

    # The accounts Stage 8 file also contains a trailing DESCRIBE.
    # Allow read-only validation statements, but never silently discard
    # another DDL or DML statement.
    for trailing in statements[1:]:
        if not re.match(r"^(DESCRIBE|SHOW)\b", trailing, re.IGNORECASE):
            raise FlinkRuntimeError(
                "UNEXPECTED_MULTIPLE_SQL_STATEMENTS"
            )

    return statements[0] + ";"


def collect_strings(value):
    """Collect string values from a JSON result without printing them."""
    if isinstance(value, str):
        yield value

    elif isinstance(value, dict):
        for child in value.values():
            yield from collect_strings(child)

    elif isinstance(value, list):
        for child in value:
            yield from collect_strings(child)


def inspect_table(runtime, step):
    """Return the CREATE TABLE definition from Flink."""
    inspect_sql = load_sql(step.inspect_file)
    rows = runtime.query(inspect_sql)

    if not rows:
        raise FlinkRuntimeError(
            f"TABLE_INSPECTION_EMPTY_{step.table.upper()}"
        )

    definition = "\n".join(collect_strings(rows))

    if not definition.strip():
        raise FlinkRuntimeError(
            f"TABLE_DEFINITION_UNAVAILABLE_{step.table.upper()}"
        )

    return definition


def assess_definition(definition, step):
    """Determine whether the requested table property is present."""
    if step.kind == "primary_key":
        keys = re.findall(
            r"\bPRIMARY\s+KEY\s*\(([^)]*)\)",
            definition,
            re.IGNORECASE,
        )

        if not keys:
            return "MISSING"

        normalized = [
            re.sub(r"[`\s]", "", key).lower()
            for key in keys
        ]

        if len(normalized) == 1 and normalized[0] == step.expected.lower():
            return "PRESENT"

        return "CONFLICT"

    if step.kind == "changelog":
        modes = re.findall(
            r"""['"`]?changelog\.mode['"`]?\s*=\s*['"`]?([a-z_-]+)""",
            definition,
            re.IGNORECASE,
        )

        if not modes:
            return "MISSING"

        if all(mode.lower() == step.expected.lower() for mode in modes):
            return "PRESENT"

        return "CONFLICT"

    raise FlinkRuntimeError("UNKNOWN_DDL_VALIDATION_TYPE")



def validate_ddl(step, ddl):
    """Ensure a versioned SQL file matches the intended operation."""
    normalized = re.sub(r"\s+", " ", ddl).strip()

    if not re.match(r"^ALTER\s+TABLE\b", normalized, re.IGNORECASE):
        raise FlinkRuntimeError("UNAUTHORIZED_DDL_OPERATION")

    target = re.search(
        r"^ALTER\s+TABLE\s+(.+?)\s+(?:ADD|SET)\b",
        normalized,
        re.IGNORECASE,
    )

    if not target:
        raise FlinkRuntimeError("DDL_TARGET_UNAVAILABLE")

    actual_table = target.group(1).replace("`", "").lower()
    expected_suffix = f"payments.public.{step.table}".lower()

    if not actual_table.endswith(expected_suffix):
        raise FlinkRuntimeError("DDL_TARGET_MISMATCH")

    if step.kind == "primary_key":
        pattern = (
            r"ADD\s+CONSTRAINT\s+[A-Za-z0-9_]+\s+"
            r"PRIMARY\s+KEY\s*\(\s*"
            + re.escape(step.expected)
            + r"\s*\)\s+NOT\s+ENFORCED"
        )

        if not re.search(pattern, normalized, re.IGNORECASE):
            raise FlinkRuntimeError("DDL_PRIMARY_KEY_MISMATCH")

    elif step.kind == "changelog":
        pattern = (
            r"""SET\s*\(\s*['"]?changelog\.mode['"]?"""
            r"""\s*=\s*['"]?append['"]?\s*\)"""
        )

        if not re.search(pattern, normalized, re.IGNORECASE):
            raise FlinkRuntimeError("DDL_CHANGELOG_MISMATCH")

    else:
        raise FlinkRuntimeError("UNKNOWN_DDL_VALIDATION_TYPE")

    return True


def apply_step(runtime, step):
    """Apply one DDL only when the desired state is not already present."""
    definition = inspect_table(runtime, step)
    state = assess_definition(definition, step)

    if state == "PRESENT":
        return "ALREADY_CONFIGURED"

    if state == "CONFLICT":
        raise FlinkRuntimeError(
            f"TABLE_CONFIGURATION_CONFLICT_{step.table.upper()}"
        )

    # Use stable names to prevent silently creating duplicate statements.
    existing = runtime.find_statement(step.name)

    if existing is not None:
        phase = runtime.statement_phase(existing)

        if phase == "COMPLETED":
            raise FlinkRuntimeError(
                f"PREVIOUS_STATEMENT_COMPLETED_WITHOUT_EXPECTED_STATE_{step.table.upper()}"
            )

        if phase not in {"PENDING", "PROVISIONING", "RUNNING"}:
            raise FlinkRuntimeError(
                "EXISTING_STATEMENT_REQUIRES_MANUAL_REVIEW"
            )

        runtime.wait_for_statement(step.name)

    else:
        ddl = load_sql(step.ddl_file)
        validate_ddl(step, ddl)

        runtime.create_statement(
            step.name,
            ddl,
            wait=True,
        )

        runtime.wait_for_statement(step.name)

    # Verify the actual table definition after the statement completes.
    definition = inspect_table(runtime, step)
    final_state = assess_definition(definition, step)

    if final_state != "PRESENT":
        raise FlinkRuntimeError(
            f"DDL_POST_VALIDATION_FAILED_{step.table.upper()}"
        )

    return "APPLIED"


def preflight_tables(runtime):
    """Inspeciona todas as alterações antes de qualquer DDL remoto.

    Retorna somente metadados de controle, nunca o conteúdo
    das tabelas ou as respostas completas do Flink.
    """
    plan = []

    for step in STEPS:
        definition = inspect_table(runtime, step)
        state = assess_definition(definition, step)

        if state == "CONFLICT":
            raise FlinkRuntimeError(
                f"FLINK_PREFLIGHT_CONFLICT_{step.table.upper()}_{step.kind.upper()}"
            )

        if state == "MISSING":
            # Validar o contrato SQL agora, antes da primeira alteração.
            validate_ddl(step, load_sql(step.ddl_file))

            # Um statement anterior não pode ser ignorado apenas
            # porque a configuração ainda não apareceu no catálogo.
            existing = runtime.find_statement(step.name)

            if existing is not None:
                phase = runtime.statement_phase(existing)
                if phase not in {"PENDING", "PROVISIONING", "RUNNING"}:
                    raise FlinkRuntimeError(
                        "FLINK_PREFLIGHT_EXISTING_STATEMENT_REQUIRES_REVIEW"
                    )

        plan.append({
            "step": step,
            "state": state,
        })

    return plan


def prepare_tables(runtime):
    """Executa alterações somente após preflight global aprovado.

    O Flink não oferece atomicidade entre estes DDLs. Em falhas
    remotas, uma nova execução deverá reavaliar o estado real.
    """
    plan = preflight_tables(runtime)
    results = []

    for item in plan:
        step = item["step"]

        if item["state"] == "PRESENT":
            outcome = "ALREADY_CONFIGURED"
        else:
            # apply_step realiza nova inspeção e pós-validação,
            # protegendo também contra mudanças entre as fases.
            outcome = apply_step(runtime, step)

        results.append({
            "step": step.name,
            "table": step.table,
            "result": outcome,
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Prepare Flink source table metadata."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Authorize remote Flink DDL execution.",
    )

    args = parser.parse_args()

    # Sem --apply, apenas leitura do catálogo e statements.
    runtime = FlinkRuntime.from_terraform_state()

    if not args.apply:
        plan = preflight_tables(runtime)

        print("=== FLINK PREFLIGHT ===")
        for item in plan:
            print(
                f"{item['step'].name}: {item['state']}"
            )

        print("FLINK_PREFLIGHT=PASSED")
        print("REMOTE_DDL_EXECUTED=False")
        return 0

    # Com --apply, a preparação ainda exige preflight global.
    results = prepare_tables(runtime)

    for result in results:
        print(f"{result['step']}: {result['result']}")

    print("FLINK_TABLE_PREPARATION=COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
