"""Inspeciona a chave primaria de accounts via Flink REST API.

Nao imprime credenciais, payloads de erro ou dados transacionais.
O statement criado sera excluido ao final, inclusive em caso de falha.
"""

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from safety import load_env_file

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra/terraform"
SUBJECT = "payments.public.accounts"

def fail(code):
    print("ERROR_CODE=", code)
    print("STAGE8_DESCRIBE_GATE=BLOCKED")
    raise SystemExit(1)

def request(url, key, secret, method="GET", payload=None):
    token = base64.b64encode(
        f"{key}:{secret}".encode()
    ).decode("ascii")

    body = json.dumps(payload).encode() if payload is not None else None

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        import re

        code = error.code

        # Le o erro localmente, sem imprimir o payload original.
        # Somente categorias previamente autorizadas sao exibidas.
        try:
            raw = error.read(16384).decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        finally:
            error.close()

        if code == 403:
            categories = {
                "FLINK_ROLE": r"flinkdeveloper|flinkadmin|flink.developer",
                "ASSIGNER": r"assigner|delegate|delegation",
                "COMPUTE_POOL": r"compute.pool|compute_pool|lfcp-",
                "PRINCIPAL": r"principal|service.account|identity",
                "CATALOG": r"catalog|database",
                "KAFKA": r"kafka|topic|transactional",
                "SCHEMA_REGISTRY": r"schema.registry|subject",
                "PERMISSION": r"permission|privilege|authorization|access.denied",
            }

            print("HTTP_403_DIAGNOSTIC=True")
            print("ERROR_BODY_AVAILABLE=", bool(raw.strip()))

            # Extrai apenas codigos e classificacoes reconhecidas.
            # Mensagens originais, identificadores e valores nao sao exibidos.

            try:
                error_document = json.loads(raw)
            except (ValueError, TypeError):
                error_document = {}

            if not isinstance(error_document, dict):
                error_document = {}

            error_items = error_document.get("errors", [])
            if not isinstance(error_items, list):
                error_items = []

            candidates = [error_document] + [
                item for item in error_items if isinstance(item, dict)
            ]

            for item in candidates[:3]:
                error_code = item.get("code", item.get("error_code"))
                if isinstance(error_code, int):
                    print("CONFLUENT_ERROR_CODE=", error_code)

            messages = " ".join(
                str(item.get("message", ""))
                for item in candidates
            ).lower()

            checks = {
                "CREATE_STATEMENT_DENIED":
                    ("create" in messages and "statement" in messages),
                "COMPUTE_POOL_ACCESS_DENIED":
                    ("compute pool" in messages or "compute_pool" in messages),
                "SERVICE_ACCOUNT_DELEGATION":
                    ("assigner" in messages or "delegate" in messages),
                "MISSING_FLINK_ROLE":
                    ("flinkdeveloper" in messages or "flinkadmin" in messages),
                "MISSING_DATA_ACCESS":
                    ("topic" in messages or "schema registry" in messages),
                "API_KEY_SCOPE":
                    ("api key" in messages or "api_key" in messages),
                "REQUIRED_PERMISSIONS":
                    ("required permissions" in messages),
                "NOT_AUTHORIZED":
                    ("not authorized" in messages or "unauthorized" in messages),
                "FORBIDDEN":
                    ("forbidden" in messages),
            }

            print("ERROR_JSON_PARSED=", bool(error_document))

            # Inspeciona a estrutura, sem expor valores livres.
            # A resposta pode usar campos diferentes de "message".
            safe_fields = {
                "code", "error_code", "status", "message",
                "detail", "title", "error", "errors", "type",
                "reason", "description"
            }

            def inspect_error(obj, level=0):
                if not isinstance(obj, dict) or level > 2:
                    return

                names = sorted(set(obj) & safe_fields)
                print("ERROR_FIELDS_LEVEL_" + str(level) + "=",
                      ",".join(names) or "NONE")

                for field in ("code", "error_code", "status"):
                    value = obj.get(field)
                    if type(value) is int and 100 <= value <= 999999:
                        print("ERROR_NUMERIC_" + field.upper() + "=", value)

                for field in ("message", "detail", "title", "error",
                              "reason", "description"):
                    value = obj.get(field)
                    if not isinstance(value, str):
                        continue

                    normalized = value.lower()
                    checks = {
                        "ACCESS_DENIED": "access denied",
                        "PERMISSION_DENIED": "permission denied",
                        "INSUFFICIENT_PERMISSIONS": "insufficient permission",
                        "REQUIRED_PERMISSIONS": "required permission",
                        "NOT_PERMITTED": "not permitted",
                        "NOT_AUTHORIZED": "not authorized",
                        "UNAUTHORIZED": "unauthorized",
                        "FORBIDDEN": "forbidden",
                        "MISSING_PRIVILEGE": "missing privilege",
                        "INVALID_PRINCIPAL": "invalid principal",
                        "INVALID_API_KEY": "invalid api key",
                        "CANNOT_CREATE": "cannot create",
                    }
                    matched = [
                        name for name, phrase in checks.items()
                        if phrase in normalized
                    ]
                    print("ERROR_TEXT_FIELD=", field)
                    print("ERROR_TEXT_CLASS=",
                          ",".join(matched) or "UNCLASSIFIED")

                nested = obj.get("errors")
                if isinstance(nested, list):
                    print("ERROR_NESTED_COUNT=", len(nested))
                    for child in nested[:2]:
                        inspect_error(child, level + 1)

            inspect_error(error_document)

            # Inspeciona o campo detail real, inclusive dentro de errors[].
            # Imprime somente palavras de uma lista controlada.
            # Nenhum trecho livre da resposta e exibido.
            import re

            details = [
                item.get("detail", "")
                for item in candidates[:3]
                if isinstance(item.get("detail"), str)
            ]

            allowed = {
                "you", "do", "not", "have", "the", "required",
                "permissions", "permission", "to", "create",
                "execute", "run", "statement", "statements",
                "on", "this", "resource", "principal", "assigner",
                "flinkdeveloper", "flinkadmin", "environment",
                "compute", "pool", "service", "account",
                "role", "binding", "access", "denied",
                "insufficient", "authorization", "forbidden",
                "kafka", "topic", "schema", "registry",
                "transactional", "id", "read", "write",
                "manage", "describe", "catalog", "database",
                "operator", "missing", "must", "be", "granted",
                "cannot", "is", "allowed", "authenticated",
                "identity", "delegate", "delegation",
            }

            print("ERROR_DETAIL_COUNT=", len(details))

            for index, detail in enumerate(details):
                words = re.findall(r"[a-zA-Z]+", detail.lower())
                sanitized = [
                    word if word in allowed else "[REDACTED]"
                    for word in words[:60]
                ]
                print(
                    "ERROR_DETAIL_SAFE_TOKENS_" + str(index) + "=",
                    " ".join(sanitized)
                )

            for item in candidates[:3]:
                for field in ("code", "status"):
                    value = item.get(field)
                    if isinstance(value, str):
                        if re.fullmatch(r"[A-Z_]{2,60}", value):
                            print("ERROR_" + field.upper() + "=", value)
                    elif isinstance(value, int):
                        print("ERROR_" + field.upper() + "=", value)



            for label, matched in checks.items():
                print(f"ERROR_DETAIL_{label}=", matched)


            for label, pattern in categories.items():
                matched = bool(re.search(pattern, raw, re.IGNORECASE))
                print(f"ERROR_CATEGORY_{label}=", matched)

        return code, {}
    except Exception:
        return 0, {}

def state_resource(state, kind, name):
    matches = [
        instance.get("attributes") or {}
        for resource in state.get("resources", [])
        if resource.get("mode") == "managed"
        and resource.get("type") == kind
        and resource.get("name") == name
        for instance in resource.get("instances", [])
    ]
    return matches[0] if len(matches) == 1 else None

def main():
    print("========== ETAPA 8 — DESCRIBE ACCOUNTS ==========")

    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if branch.stdout.strip() != "etapa-8":
        fail("WRONG_BRANCH")

    env = dict(os.environ)
    for name, value in load_env_file(ROOT / ".env").items():
        if value and not env.get(name):
            env[name] = value

    cloud_key = (
        env.get("CONFLUENT_CLOUD_API_KEY")
        or env.get("TF_VAR_confluent_cloud_api_key")
        or env.get("TF_VAR_confluent_api_key")
    )
    cloud_secret = (
        env.get("CONFLUENT_CLOUD_API_SECRET")
        or env.get("TF_VAR_confluent_cloud_api_secret")
        or env.get("TF_VAR_confluent_api_secret")
    )

    if not cloud_key or not cloud_secret:
        fail("CLOUD_CREDENTIALS_MISSING")

    # A consulta da organizacao pode falhar transitoriamente.
    # Fazemos no maximo tres tentativas, sem imprimir o payload.
    organization_status = None
    items = []

    for attempt in range(1, 4):
        organization_status, organizations = request(
            "https://api.confluent.cloud/org/v2/organizations",
            cloud_key,
            cloud_secret,
        )

        items = (
            organizations.get("data", [])
            if isinstance(organizations, dict)
            else []
        )

        print("ORGANIZATION_ATTEMPT=", attempt)
        print("ORGANIZATION_HTTP_STATUS=", organization_status)
        print(
            "ORGANIZATION_COUNT=",
            len(items) if isinstance(items, list) else "INVALID",
        )

        if (
            organization_status == 200
            and isinstance(items, list)
            and len(items) == 1
            and isinstance(items[0], dict)
            and items[0].get("id")
        ):
            break

        if organization_status in (401, 403):
            fail("ORGANIZATION_AUTHORIZATION_DENIED")

        if attempt < 3:
            time.sleep(attempt * 2)

    else:
        fail("ORGANIZATION_LOOKUP_FAILED")

    org_id = items[0]["id"]
    print("ORGANIZATION_RESOLVED=True")

    state_result = subprocess.run(
        ["terraform", "state", "pull"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    if state_result.returncode != 0:
        fail("STATE_UNAVAILABLE")

    state = json.loads(state_result.stdout)

    key = state_resource(state, "confluent_api_key", "flink_processor")
    service_account = state_resource(
        state, "confluent_service_account", "flink_processor"
    )
    pool = state_resource(
        state, "confluent_flink_compute_pool", "payment_fraud"
    )
    environment = state_resource(
        state, "confluent_environment", "challenge"
    )
    cluster = state_resource(
        state, "confluent_kafka_cluster", "basic"
    )

    # Nao presumir o nome interno do recurso Kafka.
    if cluster is None:
        clusters = [
            instance.get("attributes") or {}
            for resource in state.get("resources", [])
            if resource.get("mode") == "managed"
            and resource.get("type") == "confluent_kafka_cluster"
            for instance in resource.get("instances", [])
        ]
        cluster = clusters[0] if len(clusters) == 1 else None

    if not all((key, service_account, pool, environment, cluster)):
        fail("REQUIRED_RESOURCE_MISSING")

    if pool.get("region") != "us-east-1" or pool.get("cloud") != "AWS":
        fail("UNEXPECTED_REGION")

    if not all((
        key.get("id"),
        key.get("secret"),
        pool.get("id"),
        environment.get("id"),
        cluster.get("display_name"),
    )):
        fail("INCOMPLETE_RESOURCE_CONFIGURATION")

    base = (
        "https://flink.us-east-1.aws.confluent.cloud"
        f"/sql/v1/organizations/{org_id}"
        f"/environments/{environment['id']}/statements"
    )

    sql = (
        f"DESCRIBE `desafio-final`."
        f"`{cluster['display_name']}`.`{SUBJECT}`;"
    )

    name = "stage8-describe-" + uuid.uuid4().hex[:12]

    payload = {
        "name": name,
        "organization_id": org_id,
        "environment_id": environment["id"],
        "spec": {
            "statement": sql,
            # Explicita a mesma identidade proprietaria da API Key.
            "principal": service_account["id"],
            "compute_pool_id": pool["id"],
            "properties": {
                "sql.current-catalog": "desafio-final",
                "sql.current-database": cluster["display_name"],
            },
            "stopped": False,
        },
    }

    statement_url = base + "/" + name
    created = False
    delete_status = None
    outcome = "BLOCKED"
    error_code = None
    phase = "UNKNOWN"
    found_account_id = False

    try:
        status, _ = request(
            base, key["id"], key["secret"],
            method="POST", payload=payload
        )

        print("SUBMIT_HTTP_STATUS=", status)

        if status not in (200, 201, 202):
            error_code = "STATEMENT_SUBMISSION_FAILED"
            return

        created = True

        for _ in range(15):
            status, detail = request(
                statement_url, key["id"], key["secret"]
            )

            if status != 200:
                error_code = "STATEMENT_STATUS_FAILED"
                break

            phase = (detail.get("status") or {}).get("phase", "UNKNOWN")

            if phase in ("COMPLETED", "RUNNING"):
                break

            if phase in ("FAILED", "FAILING"):
                error_code = "SQL_EXECUTION_FAILED"
                break

            time.sleep(2)

        print("STATEMENT_PHASE=", phase)

        # Diagnostico do Flink capturado antes de excluir o statement.
        # Nao exibe mensagens livres, IDs ou dados do ambiente.
        import re

        detail = (detail.get("status") or {}).get("detail", "")

        categories = {
            "TABLE_NOT_FOUND": r"table.*not.*(found|exist)|unknown table",
            "CATALOG_NOT_FOUND": r"catalog.*not.*(found|exist)",
            "DATABASE_NOT_FOUND": r"database.*not.*(found|exist)",
            "SQL_SYNTAX": r"parse failed|syntax error|sql parse",
            "PERMISSION": r"permission|not authorized|access denied",
            "SCHEMA": r"schema|serialization|deserialization",
            "TOPIC": r"topic.*not.*(found|exist)|unknown topic",
            "VALIDATION": r"validationexception|validation error",
        }

        print("EXECUTION_DETAIL_PRESENT=", bool(detail))

        for category, pattern in categories.items():
            print(
                "SQL_ERROR_" + category + "=",
                bool(re.search(pattern, detail, re.IGNORECASE))
            )

        # Preserva apenas palavras reconhecidas para diagnostico.
        allowed = {
            "table", "catalog", "database", "topic",
            "not", "found", "does", "exist", "unknown",
            "schema", "invalid", "syntax", "parse", "failed",
            "permission", "denied", "access", "authorized",
            "cannot", "resolve", "identifier", "column",
            "primary", "key", "constraint", "describe",
            "statement", "error", "validation", "exception",
            "is", "the", "in", "of", "for", "to",
        }

        words = re.findall(r"[A-Za-z]+", detail.lower())
        safe_words = [
            word if word in allowed else "[REDACTED]"
            for word in words[:50]
        ]

        print("SQL_ERROR_SAFE_TOKENS=", " ".join(safe_words))


        if error_code:
            return

        if phase not in ("COMPLETED", "RUNNING"):
            error_code = "STATEMENT_TIMEOUT"
            return

        result_status, result = request(
            statement_url + "/results",
            key["id"], key["secret"]
        )

        print("RESULTS_HTTP_STATUS=", result_status)

        if result_status != 200:
            error_code = "RESULTS_UNAVAILABLE"
            return

        rows = (result.get("results") or {}).get("data", [])

        print("METADATA_ROWS=", len(rows))

        for item in rows:
            row = item.get("row", []) if isinstance(item, dict) else []

            if not row or str(row[0]).lower() != "account_id":
                continue

            found_account_id = True

            # DESCRIBE retorna: name, type, null, key, ...
            data_type = str(row[1]) if len(row) > 1 else "UNKNOWN"
            nullable = str(row[2]) if len(row) > 2 else "UNKNOWN"
            key_info = str(row[3]) if len(row) > 3 else "UNKNOWN"

            print("ACCOUNT_ID_FOUND=True")
            print("ACCOUNT_ID_TYPE=", data_type[:80])
            print("ACCOUNT_ID_NULLABLE=", nullable[:20])
            print("ACCOUNT_ID_KEY=", key_info[:100])

        outcome = "PASS" if found_account_id else "BLOCKED"

        if not found_account_id:
            error_code = "ACCOUNT_ID_NOT_VISIBLE"

    finally:
        # Excluir apenas o statement criado nesta execucao.
        # Se a resposta do POST foi ambigua, nao excluir cegamente.
        if created:
            delete_status, _ = request(
                statement_url,
                key["id"],
                key["secret"],
                method="DELETE",
            )

        print("CLEANUP_HTTP_STATUS=", delete_status)

        if created and delete_status in (200, 202, 204):
            import time
            cleanup_confirmed = False

            for attempt in range(8):
                check_status, _ = request(
                    statement_url, key["id"], key["secret"]
                )

                if check_status == 404:
                    cleanup_confirmed = True
                    break

                if attempt < 7:
                    time.sleep(2)

            print("STATEMENT_CLEANUP_CONFIRMED=", cleanup_confirmed)
        elif created:
            print("STATEMENT_CLEANUP_CONFIRMED=False")
        print("SQL_TYPE=DESCRIBE")
        print("ALTER_TABLE_EXECUTED=False")
        print("CDC_CONNECTOR_ACTIVATED=False")
        print("SECRET_VALUES_PRINTED=False")

        if error_code:
            print("ERROR_CODE=", error_code)

        print("STAGE8_DESCRIBE_GATE=", outcome)

        if outcome != "PASS":
            raise SystemExit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Nao imprimir excecoes brutas que possam conter URLs
        # ou informacoes internas de autenticacao.
        print("STAGE8_DESCRIBE_GATE=BLOCKED")
        print("ERROR_CODE=UNEXPECTED_EXECUTION_ERROR")
        raise SystemExit(1)
