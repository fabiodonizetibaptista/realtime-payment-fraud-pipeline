"""Etapa 9: valida resultado real do Temporal Join.

Utiliza apenas o SQL original e a CLI autenticada.
Cria e remove somente recursos temporarios com nome exclusivo.
Nunca imprime registros, IDs, endpoints ou credenciais.
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path.cwd()
TF = ROOT / "infra/terraform"
SQL = ROOT / "sql/etapa-9/04_temporal_join.sql"

ENV = dict(os.environ, TF_LOG="OFF", TF_INPUT="0")
ENV.pop("TF_LOG_PATH", None)

suffix = uuid.uuid4().hex[:16]
table_name = f"etapa9_temporal_validacao_{suffix}"
statement_name = f"etapa9-temporal-{suffix}"
catalog = "`desafio-final`.`desafio-basic`"
target = f"{catalog}.`{table_name}`"


def run(args, cwd=ROOT, timeout=90):
    try:
        return subprocess.run(
            args, cwd=cwd, env=ENV,
            capture_output=True, text=True,
            errors="replace", timeout=timeout,
            check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse(result):
    if result is None or result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return None


def resource(state, kind):
    items = [
        inst.get("attributes") or {}
        for obj in state.get("resources", [])
        if obj.get("mode") == "managed"
        and obj.get("type") == kind
        for inst in obj.get("instances", [])
    ]
    if len(items) != 1 or not items[0].get("id"):
        raise RuntimeError("RESOURCE_REFERENCE_UNAVAILABLE")
    return str(items[0]["id"])


def diagnose(result):
    if result is None:
        return "TIMEOUT_OR_COMMAND_ERROR"

    text = (result.stderr + "\n" + result.stdout).lower()
    categories = {
        "AUTH": ("not logged in", "unauthorized"),
        "PERMISSION": ("permission denied", "forbidden"),
        "SQL_VALIDATION": ("validationexception", "sql validation",
                           "column", "not found in table"),
        "ROWTIME": ("rowtime", "watermark"),
        "CHANGELOG": ("changelog", "retract"),
        "TIMEOUT": ("deadline exceeded", "timed out"),
        "QUOTA": ("quota exceeded", "resource exhausted"),
    }
    matches = [
        key for key, values in categories.items()
        if any(v in text for v in values)
    ]
    return ",".join(matches) or "UNCLASSIFIED"


print("========== ETAPA 9 — TEMPORAL JOIN REAL DATA ==========")

# A consulta permanece condicionada aos preflights de SQL,
# Terraform State e autenticacao, nao a uma branch historica.
if not SQL.is_file():
    raise SystemExit("BLOCKED_ORIGINAL_SQL_MISSING")

current = parse(run(["terraform", "state", "pull"], TF, 30))
if not isinstance(current, dict):
    raise SystemExit("BLOCKED_TERRAFORM_STATE")

try:
    environment = resource(current, "confluent_environment")
    cluster = resource(current, "confluent_kafka_cluster")
    pool = resource(current, "confluent_flink_compute_pool")
except RuntimeError:
    raise SystemExit("BLOCKED_RESOURCE_REFERENCE")

auth = run(["confluent", "environment", "list", "-o", "json"], timeout=25)
if auth is None or auth.returncode != 0:
    raise SystemExit("BLOCKED_CLI_AUTHENTICATION")

flags = [
    "--compute-pool", pool,
    "--database", cluster,
    "--environment", environment,
    "--cloud", "aws",
    "--region", "us-east-1",
]

# Remove apenas comentarios iniciais e BOM da copia em memoria.
# O arquivo SQL original nunca e modificado.
raw = SQL.read_text(encoding="utf-8-sig").strip()
removed_comments = 0

while True:
    if raw.startswith("--"):
        _, separator, remainder = raw.partition("\n")
        if not separator:
            raise SystemExit("BLOCKED_SQL_ONLY_COMMENTS")
        raw = remainder.lstrip()
        removed_comments += 1
    elif raw.startswith("/*"):
        end = raw.find("*/")
        if end < 0:
            raise SystemExit("BLOCKED_UNCLOSED_SQL_COMMENT")
        raw = raw[end + 2:].lstrip()
        removed_comments += 1
    else:
        break

original = raw.rstrip(";").strip()

sql_valid = (
    original.upper().startswith("SELECT")
    and "FOR SYSTEM_TIME AS OF" in original.upper()
    and "$rowtime" in original
    and ";" not in original
)

print("LEADING_SQL_COMMENTS_REMOVED=", removed_comments)
print("ORIGINAL_SQL_STRUCTURE_VALID=", sql_valid)

if not sql_valid:
    raise SystemExit("BLOCKED_SQL_STRUCTURE_REVIEW_REQUIRED")


def query(sql, timeout=45):
    result = run([
        "confluent", "flink", "query",
        "--sql", sql,
        *flags,
        "--timeout", "35s",
        "--output", "json",
    ], timeout=timeout)

    data = parse(result)
    if isinstance(data, list) and len(data) == 1:
        return data[0], result

    return None, result


def numeric(row, field):
    if not isinstance(row, dict):
        return None
    try:
        return int(row[field])
    except (KeyError, ValueError, TypeError):
        return None


# Primeiro estabelece a cardinalidade da origem.
source_sql = f"""
SELECT
    COUNT(*) AS total,
    COUNT(DISTINCT transaction_id) AS ids_distintos
FROM {catalog}.`payments.public.transactions`
"""

source, source_result = query(source_sql)
source_total = numeric(source, "total")
source_distinct = numeric(source, "ids_distintos")

print("SOURCE_COUNT_AVAILABLE=", source_total is not None)
print("SOURCE_TRANSACTION_COUNT=", source_total)

if source_total is None or source_total == 0:
    print("SOURCE_ERROR=", diagnose(source_result))
    raise SystemExit("BLOCKED_SOURCE_COUNT")

# Confirma que o nome exclusivo nao pertence a uma tabela existente.
existing, list_result = query(f"SHOW TABLES IN {catalog}")
if list_result is None or list_result.returncode != 0:
    raise SystemExit("BLOCKED_CANNOT_VERIFY_TARGET")

if table_name in list_result.stdout:
    raise SystemExit("BLOCKED_TARGET_ALREADY_EXISTS")

creation_attempted = False
materialization_started = False
cleanup_statement = False
cleanup_table = False
gate = "PENDING"
observed_phase = None
observed_at = None
sanitized_sample = []

try:
    print("SOURCE_SQL_REUSED=True")
    print("TEMPORARY_TARGET_PREEXISTED=False")

    ctas = f"CREATE TABLE {target} AS {original}"

    creation_attempted = True
    created = run([
        "confluent", "flink", "statement", "create",
        statement_name,
        "--sql", ctas,
        *flags,
        "--property", "sql.tables.scan.idle-timeout=5s",
        "--output", "json",
    ], timeout=90)

    print("CTAS_SUBMISSION_OK=", (
        created is not None and created.returncode == 0
    ))

    if created is None or created.returncode != 0:
        print("CTAS_ERROR_CATEGORY=", diagnose(created))
    else:
        # Consulta o estado sem publicar SQL ou identificadores.
        for attempt in range(12):
            described = run([
                "confluent", "flink", "statement", "describe",
                statement_name,
                "--environment", environment,
                "--cloud", "aws",
                "--region", "us-east-1",
                "--output", "json",
            ], timeout=30)

            status = parse(described)
            phase = (
                str(status.get("status") or "").upper()
                if isinstance(status, dict) else "UNKNOWN"
            )

            if phase in ("RUNNING", "FAILED", "DEGRADED"):
                print("CTAS_PHASE=", phase)
                observed_phase = phase
                from datetime import datetime, timezone
                observed_at = datetime.now(timezone.utc).isoformat()
                materialization_started = phase == "RUNNING"

                if not materialization_started:
                    detail = str(
                        status.get("status_detail") or ""
                    ) if isinstance(status, dict) else ""
                    print(
                        "CTAS_FAILURE_CATEGORY=",
                        diagnose(subprocess.CompletedProcess(
                            args=[], returncode=1,
                            stdout="", stderr=detail
                        ))
                    )
                break

            time.sleep(5)

    if materialization_started:
        metrics_sql = f"""
        SELECT
            COUNT(*) AS total_resultado,
            COUNT(DISTINCT transaction_id) AS distintas,
            COUNT(account_id) AS account_ids_presentes,
            COUNT(amount) AS valores_presentes,
            COUNT(customer_id) AS clientes_presentes,
            COUNT(account_status) AS status_presentes,
            COUNT(country_code) AS paises_presentes
        FROM {target}
        """

        # O statement e continuo. Consultamos o resultado
        # materializado, que suporta snapshot.
        for attempt in range(5):
            metrics, result = query(metrics_sql)

            total = numeric(metrics, "total_resultado")
            distinct = numeric(metrics, "distintas")
            account_ids = numeric(metrics, "account_ids_presentes")
            amounts = numeric(metrics, "valores_presentes")
            customers = numeric(metrics, "clientes_presentes")
            statuses = numeric(metrics, "status_presentes")
            countries = numeric(metrics, "paises_presentes")

            if total is not None:
                print("RESULT_ROWS=", total)
                print("DISTINCT_TRANSACTIONS=", distinct)
                print("ACCOUNT_IDS_PRESENT=", account_ids)
                print("AMOUNTS_PRESENT=", amounts)
                print("CUSTOMER_IDS_PRESENT=", customers)
                print("ACCOUNT_STATUSES_PRESENT=", statuses)
                print("COUNTRY_CODES_PRESENT=", countries)
            else:
                print("SNAPSHOT_ERROR_CATEGORY=", diagnose(result))

            if total == source_total and distinct == source_total:
                break

            if attempt < 4:
                time.sleep(10)

        # Compara novamente a origem para identificar ingestao
        # concorrente que invalidaria a comparacao de snapshots.
        source_after, _ = query(source_sql)
        source_stable = (
            numeric(source_after, "total") == source_total
            and numeric(source_after, "ids_distintos") == source_distinct
        )

        no_loss = total == source_total and source_stable
        # Compara a cardinalidade da origem e do resultado.
        # IDs repetidos na origem nao devem reprovar o Join.
        no_duplication = (
            total is not None
            and distinct is not None
            and total == source_total
            and distinct == source_distinct
            and source_stable
        )
        enrichment = (
            total is not None and total > 0
            and customers is not None and customers > 0
            and statuses is not None and statuses > 0
            and countries is not None and countries > 0
        )

        print("SOURCE_STABLE=", source_stable)
        print("NO_LOSS=", no_loss)
        print("NO_DUPLICATION=", no_duplication)
        print("ENRICHMENT_PRESENT=", enrichment)

        gate = (
            "PASS" if all((
                no_loss, no_duplication, enrichment
            )) else "PENDING"
        )

    print("STAGE9_DATA_GATE=", gate)

    if materialization_started:
        # Uma unica consulta snapshot sobre o resultado real.
        # Os valores brutos nunca sao impressos ou persistidos.
        import hashlib
        import hmac
        import secrets

        sample_sql = f"""
        SELECT
            transaction_id, account_id, amount, currency,
            transaction_status, event_time, customer_id,
            account_status, country_code
        FROM {target}
        LIMIT 5
        """

        sample_process = run([
            "confluent", "flink", "query",
            "--sql", sample_sql,
            *flags,
            "--timeout", "35s",
            "--output", "json",
        ], timeout=50)

        raw_rows = parse(sample_process)
        private_salt = secrets.token_bytes(32)

        def pseudonym(value, prefix):
            if value is None:
                return None
            digest = hmac.new(
                private_salt,
                str(value).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()[:12]
            return prefix + "-" + digest

        def presence(value):
            return "PRESENTE" if value is not None else "NULO"

        if isinstance(raw_rows, list):
            for index, record in enumerate(raw_rows[:5], 1):
                if not isinstance(record, dict):
                    continue

                sanitized_sample.append({
                    "amostra": index,
                    "transaction_id": pseudonym(
                        record.get("transaction_id"), "TX"
                    ),
                    "account_id": pseudonym(
                        record.get("account_id"), "AC"
                    ),
                    "amount": presence(record.get("amount")),
                    "currency": presence(record.get("currency")),
                    "transaction_status": presence(
                        record.get("transaction_status")
                    ),
                    "event_time": "[OCULTO]" if
                        record.get("event_time") is not None else None,
                    "customer_id": pseudonym(
                        record.get("customer_id"), "CL"
                    ),
                    "account_status": presence(
                        record.get("account_status")
                    ),
                    "country_code": presence(
                        record.get("country_code")
                    ),
                })

        print("SANITIZED_SAMPLE_ROWS=", len(sanitized_sample))
        print("RAW_SAMPLE_PERSISTED=False")

finally:
    # Limpa exclusivamente o statement e a tabela com o nome
    # exclusivo criado nesta execucao. Nenhum recurso anterior.
    if creation_attempted:
        deletion = run([
            "confluent", "flink", "statement", "delete",
            statement_name,
            "--environment", environment,
            "--cloud", "aws",
            "--region", "us-east-1",
            "--force",
        ], timeout=60)

        cleanup_statement = (
            deletion is not None and deletion.returncode == 0
        )

        # A exclusao do statement deve preceder o DROP TABLE.
        if cleanup_statement:
            # O nome UUID e gerado exclusivamente nesta execucao.
            # Nunca executar DROP em tabelas de outras etapas.
            for cleanup_attempt in range(5):
                _, drop_process = query(
                    f"DROP TABLE IF EXISTS {target}"
                )

                if (
                    drop_process is not None
                    and drop_process.returncode == 0
                ):
                    _, verify_process = query(
                        f"SHOW TABLES IN {catalog}"
                    )

                    cleanup_table = (
                        verify_process is not None
                        and verify_process.returncode == 0
                        and table_name not in verify_process.stdout
                    )

                    if cleanup_table:
                        break

                if cleanup_attempt < 4:
                    time.sleep(3)

    print("STATEMENT_DELETE_OK=", cleanup_statement)
    print("TEMP_TABLE_DROP_OK=", cleanup_table)
    print("PREVIOUS_STAGES_MODIFIED=False")
    print("CDC_MODIFIED=False")
    print("TERRAFORM_MODIFIED=False")
    print("ORIGINAL_SQL_MODIFIED=False")
    print("SENSITIVE_VALUES_PRINTED=False")
    print("COMMIT_EXECUTED=False")
    print("PUSH_EXECUTED=False")

    if creation_attempted and not (cleanup_statement and cleanup_table):
        print("TEMP_RESOURCE_REVIEW_REQUIRED=True")

    # Evidencias sao persistidas somente depois da limpeza.
    evidence_ok = (
        gate == "PASS"
        and observed_phase == "RUNNING"
        and cleanup_statement
        and cleanup_table
        and len(sanitized_sample) > 0
    )

    if evidence_ok:
        from datetime import datetime, timezone
        import hashlib

        directory = ROOT / "evidencias" / "flink"
        directory.mkdir(parents=True, exist_ok=True)

        sql_evidence = directory / "01_temporal_join.sql"
        status_evidence = directory / "02_statement_execution.json"
        sample_evidence = directory / "03_enriched_sample_sanitized.json"

        # Nao sobrescrever um SQL de evidencia diferente.
        sql_bytes = SQL.read_bytes()
        if sql_evidence.exists() and sql_evidence.read_bytes() != sql_bytes:
            print("EVIDENCE_GATE=BLOCKED_SQL_CONFLICT")
        else:
            sql_evidence.write_bytes(sql_bytes)

            status_record = {
                "etapa": 9,
                "tipo": "temporal_join_ctas",
                "estado_observado": observed_phase,
                "observado_em_utc": observed_at,
                "sql_sha256": hashlib.sha256(sql_bytes).hexdigest(),
                "origem_registros": source_total,
                "origem_ids_distintos": source_distinct,
                "resultado_registros": total,
                "resultado_ids_distintos": distinct,
                "clientes_presentes": customers,
                "status_conta_presentes": statuses,
                "pais_conta_presentes": countries,
                "origem_estavel": source_stable,
                "sem_perda_agregada": no_loss,
                "sem_multiplicacao_agregada": no_duplication,
                "enriquecimento_confirmado": enrichment,
                "statement_delete_ok": cleanup_statement,
                "tabela_temporaria_drop_ok": cleanup_table,
                "nota": (
                    "Estado RUNNING observado durante o teste. "
                    "O statement foi posteriormente excluido. "
                    "A comparacao de cardinalidade e agregada."
                ),
            }

            sample_record = {
                "etapa": 9,
                "gerado_em_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "sanitizacao": (
                    "Identificadores pseudonimizados com HMAC-SHA256 "
                    "e chave efemera nao persistida. Valores e "
                    "datas reais ocultados."
                ),
                "quantidade": len(sanitized_sample),
                "registros": sanitized_sample,
            }

            status_evidence.write_text(
                json.dumps(
                    status_record, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            sample_evidence.write_text(
                json.dumps(
                    sample_record, indent=2, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            print("EVIDENCE_SQL_SAVED=True")
            print("EVIDENCE_STATEMENT_SAVED=True")
            print("EVIDENCE_SAMPLE_SAVED=True")
            print("EVIDENCE_GATE=PASS")
    else:
        print("EVIDENCE_GATE=PENDING")
        print("EVIDENCE_FILES_NOT_GENERATED=True")

    print("========== END ETAPA 9 ==========")
