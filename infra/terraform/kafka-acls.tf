# Kafka Basic utiliza ACLs para permissao em topicos e consumer groups.
# A criacao fica desabilitada no primeiro apply: a API Key do iac_admin
# precisa ser criada e exportada para KAFKA_API_KEY/KAFKA_API_SECRET antes.
# O provider Confluent recebe KAFKA_ID, KAFKA_REST_ENDPOINT e credenciais
# por variaveis de ambiente; nao colocar secrets em blocos credentials.

resource "confluent_kafka_acl" "producer_topic_write" {
  count = var.enable_kafka_acls ? 1 : 0

  resource_type = "TOPIC"
  resource_name = var.kafka_topic_prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.producer.id}"
  host          = "*"
  operation     = "WRITE"
  permission    = "ALLOW"
}

resource "confluent_kafka_acl" "consumer_topic_read" {
  count = var.enable_kafka_acls ? 1 : 0

  resource_type = "TOPIC"
  resource_name = var.kafka_topic_prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.consumer.id}"
  host          = "*"
  operation     = "READ"
  permission    = "ALLOW"
}

resource "confluent_kafka_acl" "consumer_group_read" {
  count = var.enable_kafka_acls ? 1 : 0

  resource_type = "GROUP"
  resource_name = var.kafka_topic_prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${confluent_service_account.consumer.id}"
  host          = "*"
  operation     = "READ"
  permission    = "ALLOW"
}
