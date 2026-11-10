"""Revisao segura e extensivel de planos Terraform.

Nao executa Terraform e nao autoriza apply.
Somente enderecos, tipos e acoes podem aparecer no resumo.
"""

from collections import Counter
from collections.abc import Mapping


# Providers permitidos no laboratorio.
# Novos providers exigem revisao explicita de arquitetura.
ALLOWED_TYPE_PREFIXES = ("aiven_", "confluent_")

# Destruicao e substituicao devem ter fluxos de aprovacao separados.
SAFE_ACTIONS = {("create",), ("update",)}


def review_plan(plan: Mapping) -> dict:
    """Revisa mudancas propostas sem acessar atributos sensiveis."""

    if not isinstance(plan, Mapping) or plan.get("errored") is True:
        raise ValueError("PLAN_REJECTED=INVALID_PLAN")

    changes = plan.get("resource_changes")

    if not isinstance(changes, list):
        raise ValueError("PLAN_REJECTED=MISSING_RESOURCE_CHANGES")

    seen = set()
    reviewed = []
    counts = Counter()

    for item in changes:
        if not isinstance(item, Mapping):
            raise ValueError("PLAN_REJECTED=INVALID_RESOURCE")

        address = item.get("address")
        resource_type = item.get("type")
        mode = item.get("mode")
        change = item.get("change")

        if (
            not isinstance(address, str)
            or not address
            or not isinstance(resource_type, str)
            or mode not in ("managed", "data")
            or not isinstance(change, Mapping)
            or address in seen
        ):
            raise ValueError("PLAN_REJECTED=INVALID_RESOURCE_METADATA")

        seen.add(address)
        actions = change.get("actions")

        if not isinstance(actions, list):
            raise ValueError("PLAN_REJECTED=INVALID_ACTIONS")

        action_tuple = tuple(actions)

        # Data sources may appear in Terraform plan JSON with mode="data".
        # They are read-only: never count them as managed-resource changes.
        if mode == "data":
            if action_tuple not in {("read",), ("no-op",)}:
                raise ValueError("PLAN_REJECTED=UNSAFE_DATA_SOURCE_ACTION")
            continue

        if action_tuple in {("no-op",), ("read",)}:
            continue

        if not resource_type.startswith(ALLOWED_TYPE_PREFIXES):
            raise ValueError("PLAN_REJECTED=UNKNOWN_RESOURCE_TYPE")

        if action_tuple not in SAFE_ACTIONS:
            raise ValueError("PLAN_REJECTED=UNSAFE_ACTION")

        # Nunca incluir change.before, change.after ou outputs.
        action = action_tuple[0]
        reviewed.append({"address": address, "action": action})
        counts[action] += 1

    return {
        "approved_for_review": True,
        "approved_for_apply": False,
        "create": counts["create"],
        "update": counts["update"],
        "resources": sorted(reviewed, key=lambda r: r["address"]),
    }
