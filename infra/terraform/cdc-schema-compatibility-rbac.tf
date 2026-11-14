# Etapa 6 — Permissao minima para gerenciar compatibilidade.
#
# DeveloperWrite permite registrar schemas, mas nao alterar
# a politica de compatibilidade do subject.
#
# DeveloperManage fica restrito ao contrato testado.
# Nao concede privilegios globais no Schema Registry.

resource "confluent_role_binding" "schema_registry_transactions_manage" {
  principal = "User:${confluent_service_account.schema_registry.id}"

  role_name = "DeveloperManage"

  crn_pattern = "${data.confluent_schema_registry_cluster.essentials.resource_name}/subject=payments.public.transactions-value"
}
