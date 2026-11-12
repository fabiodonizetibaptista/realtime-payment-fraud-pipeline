# ACLs do conector CDC PostgreSQL/Debezium.
#
# As permissoes usam a identidade criada pela Foundation.
# Os IDs sao referenciados dinamicamente; nenhum identificador de ambiente anterior e reutilizado.
#
# Todas as ACLs permanecem desabilitadas ate a exportacao das credenciais
# administrativas e a ativacao explicita da segunda fase.

resource "confluent_kafka_acl" "cdc_topic_write" {
  count = var.enable_cdc_acls ? 1 : 0

  resource_type = "TOPIC"
  resource_name = var.cdc_topic_prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.cdc.id}"
  host          = "*"
  operation     = "WRITE"
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

resource "confluent_kafka_acl" "cdc_topic_create" {
  count = var.enable_cdc_acls ? 1 : 0

  resource_type = "TOPIC"
  resource_name = var.cdc_topic_prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.cdc.id}"
  host          = "*"
  operation     = "CREATE"
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

resource "confluent_kafka_acl" "cdc_cluster_describe" {
  count = var.enable_cdc_acls ? 1 : 0

  resource_type = "CLUSTER"
  resource_name = "kafka-cluster"
  pattern_type  = "LITERAL"
  principal     = "User:${confluent_service_account.cdc.id}"
  host          = "*"
  operation     = "DESCRIBE"
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

resource "confluent_kafka_acl" "cdc_cluster_describe_configs" {
  count = var.enable_cdc_acls ? 1 : 0

  resource_type = "CLUSTER"
  resource_name = "kafka-cluster"
  pattern_type  = "LITERAL"
  principal     = "User:${confluent_service_account.cdc.id}"
  host          = "*"
  operation     = "DESCRIBE_CONFIGS"
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

# O ID do conector faz parte do nome do heartbeat Debezium.
# O prefixo evita vincular a permissao a um identificador de outra implantacao.
resource "confluent_kafka_acl" "cdc_heartbeat" {
  for_each = var.enable_cdc_acls ? toset([
    "CREATE",
    "DESCRIBE",
    "WRITE"
  ]) : toset([])

  resource_type = "TOPIC"
  resource_name = "__debezium-heartbeat-"
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.cdc.id}"
  host          = "*"
  operation     = each.value
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}
