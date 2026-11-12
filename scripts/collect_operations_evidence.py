"""Etapa 13: inventario e billing sanitizados da Confluent.

plan: valida o plano localmente.
collect --confirm-read: consulta a Confluent e exporta evidencias.

Nao cria recursos, nao imprime respostas brutas nem credenciais.
Environment e cluster sao informados explicitamente (--environment/--cluster);
a sessao ativa da CLI nao e usada para escolher o escopo.
"""

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".local" / "etapa13-evidencias.json"


def rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("UNEXPECTED_RESPONSE_STRUCTURE")


def query(*args):
    """Executa somente comandos GET/list/describe da CLI."""
    result = subprocess.run(
        ["confluent", *args, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("CONFLUENT_READ_FAILED")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError("INVALID_JSON_RESPONSE") from None


def active_environment(environments):
    current = [e for e in environments if e.get("is_current")]
    if len(current) != 1 or not current[0].get("id"):
        raise ValueError("ACTIVE_ENVIRONMENT_NOT_RESOLVED")
    return current[0]


def select_environment(environments, env_id):
    """Escolhe o environment pelo ID explicito, nunca pela sessao ativa."""
    matches = [e for e in environments if e.get("id") == env_id]
    if len(matches) != 1:
        raise ValueError("ENVIRONMENT_NOT_FOUND")
    return matches[0]


def amount(value):
    """Converte valores de billing sem arredondar."""
    try:
        return Decimal(
            str(value).replace("$", "").replace(",", "").strip()
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("INVALID_BILLING_AMOUNT") from None


def environment_id(item):
    env = item.get("environment")
    if isinstance(env, dict):
        return env.get("id")
    if isinstance(env, str):
        return env
    resource = item.get("resource")
    if isinstance(resource, dict):
        nested = resource.get("environment")
        if isinstance(nested, dict):
            return nested.get("id")
        if isinstance(nested, str):
            return nested
    return None


def summarize_billing(items, selected_environment):
    """Separa despesas identificadas, outros ambientes e creditos.

    Nao distribui creditos promocionais globais entre ambientes.
    """
    by_product = {}
    unattributed = 0
    excluded = 0
    credits = Decimal("0")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("INVALID_BILLING_ROW")

        line_type = str(item.get("line_type", "")).upper()
        value = amount(item.get("amount"))

        if line_type == "PROMO_CREDIT":
            credits += value
            continue

        env = environment_id(item)
        if env is None:
            unattributed += 1
            continue
        if env != selected_environment:
            excluded += 1
            continue

        product = str(item.get("product") or "UNCLASSIFIED")
        by_product[product] = (
            by_product.get(product, Decimal("0")) + value
        )

    return {
        "by_product_usd": {
            key: str(value)
            for key, value in sorted(by_product.items())
        },
        "environment_total_usd": str(sum(
            by_product.values(), Decimal("0")
        )),
        "global_promo_credits_usd": str(credits),
        "unattributed_items": unattributed,
        "other_environment_items": excluded,
        "scope": "selected_environment_before_global_credits",
    }


def collect(start, end, env_id, cluster_id):
    env = select_environment(query("environment", "list"), env_id)
    scope = ("--environment", env_id)

    clusters = rows(query("kafka", "cluster", "list", *scope))
    pools = rows(query("flink", "compute-pool", "list", *scope))
    identities = rows(query("iam", "service-account", "list"))
    acls = rows(query("kafka", "acl", "list", *scope, "--cluster", cluster_id))
    billing = rows(query(
        "billing", "cost", "list",
        "--start-date", start, "--end-date", end,
    ))

    # Campos permitidos explicitamente: sem endpoints, tokens ou
    # respostas completas da Confluent.
    cluster_inventory = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "status": c.get("status"),
            "type": c.get("type"),
            "created_at": c.get("created_at"),
        }
        for c in clusters
    ]

    pool_inventory = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "status": p.get("status"),
            "max_cfu": p.get("max_cfu"),
            "current_cfu": p.get("current_cfu"),
        }
        for p in pools
    ]

    operations = Counter(
        str(a.get("operation") or "UNKNOWN")
        for a in acls
    )

    return {
        "environment_name": env.get("name"),
        "environment_id": env_id,
        "period": {"start": start, "end_exclusive": end},
        "kafka_clusters": cluster_inventory,
        "flink_compute_pools": pool_inventory,
        "service_account_count": len(identities),
        "kafka_acl_count": len(acls),
        "acl_operations": dict(sorted(operations.items())),
        "rbac_review": "NOT_VERIFIED_FOR_ALL_IDENTITIES",
        "billing": summarize_billing(billing, env_id),
    }


def save(report):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Arquivo privado, sem publicar dados operacionais no Git.
    fd = os.open(
        OUTPUT,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print("EVIDENCE_EXPORTED=True")
    print("OUTPUT=.local/etapa13-evidencias.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "collect"))
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--confirm-read", action="store_true")
    parser.add_argument("--environment", help="ID do environment (env-...)")
    parser.add_argument("--cluster", help="ID do cluster Kafka (lkc-...)")
    args = parser.parse_args()

    if args.action == "plan":
        print("DISCOVERY=ACTIVE_CLI_ENVIRONMENT")
        print("CLUSTERS=AUTOMATED")
        print("COMPUTE_POOLS=AUTOMATED")
        print("SERVICE_ACCOUNTS=AUTOMATED")
        print("KAFKA_ACLS=AUTOMATED")
        print("BILLING=AUTOMATED")
        print("CLOUD_EXECUTION=False")
        return

    if not args.confirm_read:
        parser.error("collect exige --confirm-read")

    try:
        if not args.start_date or not args.end_date:
            raise ValueError("DATES_REQUIRED")
        if not args.environment or not args.cluster:
            raise ValueError("ENVIRONMENT_AND_CLUSTER_REQUIRED")

        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)

        if end <= start:
            raise ValueError("INVALID_DATE_RANGE")

        if OUTPUT.exists():
            raise ValueError("REPORT_ALREADY_EXISTS")

        report = collect(start.isoformat(), end.isoformat(), args.environment, args.cluster)
        save(report)

        print("CLUSTER_COUNT=" + str(len(report["kafka_clusters"])))
        print("POOL_COUNT=" + str(len(report["flink_compute_pools"])))
        print("SERVICE_ACCOUNT_COUNT=" + str(report["service_account_count"]))
        print("KAFKA_ACL_COUNT=" + str(report["kafka_acl_count"]))
        print("BILLING_SCOPE=SELECTED_ENVIRONMENT")
        print("COLLECTION=PASS")

    except (
        RuntimeError, ValueError, OSError,
        subprocess.TimeoutExpired,
    ) as error:
        # Exibe somente a categoria, nunca o retorno bruto da CLI.
        print("COLLECTION=FAIL")
        print("ERROR_TYPE=" + type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
