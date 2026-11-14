"""Etapa 13: plano de observabilidade e controle de custos.

Neste primeiro bloco, apenas prepara e valida os comandos
de consulta. Nenhuma credencial ou Terraform State e lido.
"""

import argparse
import shutil

CHECKS = {
    "CLUSTER": (
        "confluent kafka cluster describe <cluster-id> "
        "--environment <environment-id> -o json"
    ),
    "SERVICE_ACCOUNTS": (
        "confluent iam service-account list -o json"
    ),
    "ROLE_BINDINGS": (
        "confluent iam rbac role-binding list "
        "<filtros-de-escopo> -o json"
    ),
    "KAFKA_ACLS": (
        "confluent kafka acl list "
        "--cluster <cluster-id> --environment <environment-id> -o json"
    ),
    "BILLING": (
        "confluent billing cost list "
        "--start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> -o json"
    ),
}


def plan():
    print("ETAPA=13")
    print("CLUSTER_METADATA=PLANNED")
    print("SECURITY_INVENTORY=PLANNED")
    print("BILLING_REVIEW=PLANNED")

    for name, command in CHECKS.items():
        print(f"{name}_COMMAND={command}")

    print("CONFLUENT_CLI_AVAILABLE=" + str(
        shutil.which("confluent") is not None
    ))
    print("CLOUD_EXECUTION=False")
    print("RESOURCES_CREATED=0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan",))
    args = parser.parse_args()

    if args.action == "plan":
        plan()


if __name__ == "__main__":
    main()
