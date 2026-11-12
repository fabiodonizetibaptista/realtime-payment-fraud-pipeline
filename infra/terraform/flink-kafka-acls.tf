# Etapa 8 — Permissoes Kafka para o processamento Flink.
#
# O cluster Kafka Basic utiliza ACLs para autorizacao granular.
# A conexao administrativa e herdada do provider Confluent existente.
#
# As permissoes sao restritas a Service Account flink_processor.
# Nao concedemos acesso administrativo ao cluster.

# Permite leitura do topico CDC de contas.
resource "confluent_kafka_acl" "flink_accounts_topic_read" {
  resource_type = "TOPIC"
  resource_name = "payments.public.accounts"
  pattern_type  = "LITERAL"

  principal  = "User:${confluent_service_account.flink_processor.id}"
  host       = "*"
  operation  = "READ"
  permission = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

# Permite consultar o estado dos IDs transacionais do Flink.
resource "confluent_kafka_acl" "flink_transactional_id_read" {
  resource_type = "TRANSACTIONAL_ID"
  resource_name = "_confluent-flink_"
  pattern_type  = "PREFIXED"

  principal  = "User:${confluent_service_account.flink_processor.id}"
  host       = "*"
  operation  = "READ"
  permission = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}

# Permite operar transacoes do Flink para processamento exactly-once.
resource "confluent_kafka_acl" "flink_transactional_id_write" {
  resource_type = "TRANSACTIONAL_ID"
  resource_name = "_confluent-flink_"
  pattern_type  = "PREFIXED"

  principal  = "User:${confluent_service_account.flink_processor.id}"
  host       = "*"
  operation  = "WRITE"
  permission = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}
