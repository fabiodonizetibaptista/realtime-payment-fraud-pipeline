# Metadados dinamicos para as etapas seguintes. Nenhum ID da V1 e fixado.
output "environment_id" {
  description = "ID do Environment criado para o desafio."
  value       = confluent_environment.challenge.id
}

output "kafka_cluster_id" {
  description = "ID do cluster Kafka Basic."
  value       = confluent_kafka_cluster.basic.id
}

output "kafka_bootstrap_endpoint" {
  description = "Bootstrap endpoint do cluster Kafka."
  value       = confluent_kafka_cluster.basic.bootstrap_endpoint
}

output "kafka_rest_endpoint" {
  description = "REST endpoint do cluster Kafka."
  value       = confluent_kafka_cluster.basic.rest_endpoint
}

output "schema_registry_cluster_id" {
  description = "ID do Schema Registry Essentials."
  value       = data.confluent_schema_registry_cluster.essentials.id
}

output "schema_registry_rest_endpoint" {
  description = "REST endpoint do Schema Registry Essentials."
  value       = data.confluent_schema_registry_cluster.essentials.rest_endpoint
}

output "service_account_ids" {
  description = "IDs publicos das identidades criadas na Foundation."
  value = {
    iac_admin       = confluent_service_account.iac_admin.id
    producer        = confluent_service_account.producer.id
    consumer        = confluent_service_account.consumer.id
    cdc             = confluent_service_account.cdc.id
    schema_registry = confluent_service_account.schema_registry.id
  }
}

output "kafka_admin_api_key_id" {
  description = "ID da Kafka API Key administrativa."
  value       = confluent_api_key.iac_admin_kafka.id
}

output "kafka_admin_api_key_secret" {
  description = "Secret da Kafka API Key administrativa; nao imprimir no terminal."
  value       = confluent_api_key.iac_admin_kafka.secret
  sensitive   = true
}

output "producer_kafka_api_key_id" {
  description = "ID da Kafka API Key do producer."
  value       = confluent_api_key.producer_kafka.id
}

output "producer_kafka_api_key_secret" {
  description = "Secret da Kafka API Key do producer; nao imprimir no terminal."
  value       = confluent_api_key.producer_kafka.secret
  sensitive   = true
}

output "consumer_kafka_api_key_id" {
  description = "ID da Kafka API Key do consumer."
  value       = confluent_api_key.consumer_kafka.id
}

output "consumer_kafka_api_key_secret" {
  description = "Secret da Kafka API Key do consumer; nao imprimir no terminal."
  value       = confluent_api_key.consumer_kafka.secret
  sensitive   = true
}

output "schema_registry_api_key_id" {
  description = "ID da API Key do Schema Registry."
  value       = confluent_api_key.schema_registry.id
}

output "schema_registry_api_key_secret" {
  description = "Secret da API Key do Schema Registry; nao imprimir no terminal."
  value       = confluent_api_key.schema_registry.secret
  sensitive   = true
}
