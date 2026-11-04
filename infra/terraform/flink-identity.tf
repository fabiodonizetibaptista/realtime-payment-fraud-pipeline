# Etapa 7 — Identidade dedicada ao processamento Flink.
#
# Todos os recursos sao criados pelo Terraform.
# Nenhum identificador da V1 e utilizado.

# A regiao Flink deve corresponder a regiao do Compute Pool.
data "confluent_flink_region" "payment_fraud" {
  cloud  = confluent_flink_compute_pool.payment_fraud.cloud
  region = confluent_flink_compute_pool.payment_fraud.region
}

# Identidade de servico independente das credenciais administrativas.
resource "confluent_service_account" "flink_processor" {
  display_name = "payment-fraud-flink-v2"
  description  = "Service account for payment fraud Flink SQL processing"

  lifecycle {
    prevent_destroy = true
  }
}

# Principio do menor privilegio:
# permite operar statements somente no Compute Pool deste projeto.
resource "confluent_role_binding" "flink_processor_developer" {
  principal = "User:${confluent_service_account.flink_processor.id}"
  role_name = "FlinkDeveloper"

  crn_pattern = "${confluent_environment.challenge.resource_name}/flink-region=${confluent_flink_compute_pool.payment_fraud.cloud}.${confluent_flink_compute_pool.payment_fraud.region}/compute-pool=${confluent_flink_compute_pool.payment_fraud.id}"
}

# API Key especifica da regiao Flink.
# O secret permanece no State sensivel e nao deve ser exibido.
resource "confluent_api_key" "flink_processor" {
  display_name = "payment-fraud-flink-v2-key"
  description  = "Flink region API key for payment fraud processing"

  owner {
    id          = confluent_service_account.flink_processor.id
    api_version = confluent_service_account.flink_processor.api_version
    kind        = confluent_service_account.flink_processor.kind
  }

  managed_resource {
    id          = data.confluent_flink_region.payment_fraud.id
    api_version = data.confluent_flink_region.payment_fraud.api_version
    kind        = data.confluent_flink_region.payment_fraud.kind

    environment {
      id = confluent_environment.challenge.id
    }
  }

  depends_on = [
    confluent_role_binding.flink_processor_developer
  ]

  lifecycle {
    prevent_destroy = true
  }
}
