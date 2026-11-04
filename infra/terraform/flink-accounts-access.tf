# Etapa 8 — RBAC do Schema Registry para accounts.
#
# Kafka Basic nao suporta RBAC granular em topicos
# e IDs transacionais. Esses acessos usam Kafka ACLs.
#
# FlinkDeveloper permanece definido na Etapa 7.

resource "confluent_role_binding" "flink_accounts_schema_read" {
  for_each = toset([
    "payments.public.accounts-key",
    "payments.public.accounts-value",
  ])

  principal   = "User:${confluent_service_account.flink_processor.id}"
  role_name   = "DeveloperRead"
  crn_pattern = "${data.confluent_schema_registry_cluster.essentials.resource_name}/subject=${each.key}"
}
