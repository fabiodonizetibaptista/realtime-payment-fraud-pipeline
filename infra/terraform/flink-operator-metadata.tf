# Etapa 8 — Acesso de metadados do catalogo Flink.
# Operator permite consultar metadados, sem ler registros Kafka.
# Escopo restrito ao Environment do desafio.

resource "confluent_role_binding" "flink_operator_metadata" {
  principal   = "User:${confluent_service_account.flink_processor.id}"
  role_name   = "Operator"
  crn_pattern = confluent_environment.challenge.resource_name
}
