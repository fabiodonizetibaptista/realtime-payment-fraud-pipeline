"""Classificacao estruturada de falhas do conector CDC.

O texto do provider Terraform pode conter credenciais em formatos que a
redacao por valor exato nao cobre (URI com senha, PEM, base64, cabecalhos).
Por isso este modulo NUNCA persiste nem devolve trechos do texto original:
a saida contem apenas valores de um conjunto fechado (categoria e regra) e,
quando identificavel, o codigo HTTP numerico.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Ordem importa: a primeira regra que casar define a categoria.
# Regras mais especificas (PostgreSQL, TLS, slot) vem antes das genericas.
RULES = (
    ("PG_AUTH", "pg_password_auth",
     r"password authentication failed|no pg_hba\.conf entry|"
     r"role \S+ does not exist|FATAL:\s+password"),
    ("TLS_CA", "tls_certificate",
     r"\bssl\b|\btls\b|certificate|x509|sslrootcert|pkix|handshake"),
    ("REPLICATION_SLOT", "replication_slot",
     r"replication slot|max_replication_slots|slot\.name"),
    ("PUBLICATION", "publication",
     r"publication"),
    ("NETWORK", "network_unreachable",
     r"timed out|timeout|connection refused|could not connect|"
     r"no route to host|unknown host|could not translate host|"
     r"name resolution|unreachable"),
    ("KAFKA_ACL", "kafka_authorization",
     r"topicauthorization|clusterauthorization|groupauthorization|"
     r"not authorized to access|\bacls?\b"),
    ("QUOTA_LIMIT", "quota_or_limit",
     r"quota|limit exceeded|too many requests|\b429\b|"
     r"insufficient (credit|balance)"),
    ("CONFLUENT_AUTH", "confluent_auth",
     r"\b401\b|\b403\b|unauthorized|forbidden|invalid api key|"
     r"invalid credentials"),
    ("INVALID_CONFIG", "invalid_config",
     r"\b400\b|bad request|invalid config|invalid value|"
     r"validation (error|failed)|is required|unknown configuration"),
)

CATEGORIES = tuple(rule[0] for rule in RULES) + ("UNKNOWN",)
RULE_IDS = tuple(rule[1] for rule in RULES) + ("no_rule_matched",)

_COMPILED = tuple(
    (category, rule_id, re.compile(pattern, re.IGNORECASE))
    for category, rule_id, pattern in RULES
)
_HTTP_STATUS = (
    # "status code: 401", "HTTP/1.1 403", "Error: 401"
    re.compile(
        r"(?:status(?:\s*code)?|http(?:/\d(?:\.\d)?)?|error|code)\s*[:=]?\s*\(?([45]\d\d)\b",
        re.IGNORECASE,
    ),
    # "400 Bad Request", "429 Too Many Requests"
    re.compile(
        r"\b([45]\d\d)\s+(?:bad request|unauthorized|forbidden|not found|conflict|"
        r"unprocessable|too many requests|internal server error|bad gateway|"
        r"service unavailable|gateway timeout)",
        re.IGNORECASE,
    ),
)


def classify(text: str) -> dict:
    """Devolve somente categoria, regra e status HTTP numerico."""
    text = text or ""
    category, rule_id = "UNKNOWN", "no_rule_matched"
    for candidate, candidate_rule, pattern in _COMPILED:
        if pattern.search(text):
            category, rule_id = candidate, candidate_rule
            break

    http_status = None
    for pattern in _HTTP_STATUS:
        match = pattern.search(text)
        if match:
            http_status = int(match.group(1))
            break

    return {
        "category": category,
        "rule_id": rule_id,
        "http_status": http_status,
    }


MASK = "<mascarado>"
SECRET_NAME = re.compile(r"KEY|SECRET|PASSWORD|PASS|TOKEN|CERT|CA\b|_CA$", re.IGNORECASE)
_GENERIC_MASKS = (
    # Bloco PEM completo (ou truncado ate o fim do texto).
    (re.compile(r"-----BEGIN [A-Z ]+-----.*?(?:-----END [A-Z ]+-----|\Z)", re.DOTALL), "<PEM mascarado>"),
    # Credencial em URI: esquema://usuario:senha@
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^\s:/@]+:[^\s@]+@", re.IGNORECASE), r"\1<mascarado>@"),
    # "password":"x" / password=x / api_secret: x (JSON, querystring, logs)
    (re.compile(
        r"""(["']?[\w.-]*(?:password|passwd|secret|token|api[_.-]?key|sslrootcert|authorization)[\w.-]*["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}\]]+)""",
        re.IGNORECASE), r"\1" + MASK),
    # Cabecalhos Authorization
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9+/=._-]{8,}", re.IGNORECASE), r"\1 " + MASK),
    # Qualquer string longa com cara de segredo (base64/hex/JWT/token)
    (re.compile(r"[A-Za-z0-9+/=_.-]{32,}"), MASK),
)


def secret_fragments(values) -> list[str]:
    """Valores exatos e cada linha longa deles (cobre PEM e multilinha)."""
    fragments = set()
    for value in values:
        if not value or len(value) < 6:
            continue
        fragments.add(value)
        fragments.update(line.strip() for line in value.splitlines() if len(line.strip()) >= 12)
    return sorted(fragments, key=len, reverse=True)


def mask_text(text: str, secrets=()) -> str:
    """Mascara valores conhecidos e, depois, padroes genericos de segredo."""
    for fragment in secret_fragments(secrets):
        text = text.replace(fragment, MASK)
    for pattern, replacement in _GENERIC_MASKS:
        text = pattern.sub(replacement, text)
    return text


def masked_error_lines(text: str, secrets=(), limit: int = 40) -> list[str]:
    """Somente o bloco de erro do Terraform, mascarado, para exibir na tela.

    Nunca deve ser gravado em disco; o chamador apenas imprime.
    """
    lines = [re.sub(r"^[│╷╵] ?", "", line).rstrip() for line in (text or "").splitlines()]
    start = next((i for i, line in enumerate(lines) if line.strip().startswith("Error:")), None)
    if start is None:
        return []
    block = "\n".join(line for line in lines[start:] if line.strip())
    return mask_text(block, secrets).splitlines()[:limit]


def write_diagnostic(directory: Path, run_id: str, diagnostic: dict) -> Path:
    """Grava o diagnostico estruturado; recusa campos fora do contrato."""
    allowed = {"category", "rule_id", "http_status"}
    if set(diagnostic) != allowed:
        raise ValueError("DIAGNOSTIC_FIELDS_INVALID")
    if diagnostic["category"] not in CATEGORIES:
        raise ValueError("DIAGNOSTIC_CATEGORY_INVALID")
    if diagnostic["rule_id"] not in RULE_IDS:
        raise ValueError("DIAGNOSTIC_RULE_INVALID")
    status = diagnostic["http_status"]
    if status is not None and not (isinstance(status, int) and 400 <= status <= 599):
        raise ValueError("DIAGNOSTIC_STATUS_INVALID")

    record = {
        **diagnostic,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider_text_persisted": False,
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run_id}-connector.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
