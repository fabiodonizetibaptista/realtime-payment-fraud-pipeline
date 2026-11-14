# Cloud API credentials are read from CONFLUENT_CLOUD_API_KEY and
# CONFLUENT_CLOUD_API_SECRET (Codespaces Secrets).
# Kafka and Schema Registry data-plane credentials use dedicated TF_VAR_*
# variables exported from this V2 Foundation, avoiding collisions with V1.
provider "confluent" {
  kafka_id            = var.foundation_kafka_id
  kafka_rest_endpoint = var.foundation_kafka_rest_endpoint
  kafka_api_key       = var.foundation_kafka_api_key
  kafka_api_secret    = var.foundation_kafka_api_secret

  schema_registry_id            = var.foundation_schema_registry_id
  schema_registry_rest_endpoint = var.foundation_schema_registry_rest_endpoint
  schema_registry_api_key       = var.foundation_schema_registry_api_key
  schema_registry_api_secret    = var.foundation_schema_registry_api_secret
}

# The Aiven provider is intentionally configured in the next infrastructure
# block, when Aiven resources are introduced. The provider dependency remains
# pinned in versions.tf and .terraform.lock.hcl.

# Autenticacao obtida de AIVEN_TOKEN no ambiente.
# O token nao deve ser declarado no codigo nem registrado em logs.
provider "aiven" {}
