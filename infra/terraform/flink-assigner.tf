# Etapa 8 — Delegacao restrita de identidade Flink.
#
# A Service Account usada pela API Key pode atribuir
# somente a propria identidade a statements Flink.
# Nao concede administracao global ou acesso a outras SAs.

resource "confluent_role_binding" "flink_self_assigner" {
  principal = "User:${confluent_service_account.flink_processor.id}"

  role_name = "Assigner"

  crn_pattern = "${split("/environment=", confluent_environment.challenge.resource_name)[0]}/service-account=${confluent_service_account.flink_processor.id}"
}
