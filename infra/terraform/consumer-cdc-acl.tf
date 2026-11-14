# Permissao adicional do consumidor para os topicos CDC.
# Mantem intactas as ACLs existentes da Foundation.

resource "confluent_kafka_acl" "consumer_payments_topic_read" {
  count = var.enable_kafka_acls ? 1 : 0

  resource_type = "TOPIC"
  resource_name = "payments."
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.consumer.id}"
  host          = "*"
  operation     = "READ"
  permission    = "ALLOW"

  # O provider usa credenciais por variavel; sem esta aresta o destroy
  # removeria a chave/cluster antes da ACL (401 no teardown).
  depends_on = [confluent_api_key.iac_admin_kafka]
}
