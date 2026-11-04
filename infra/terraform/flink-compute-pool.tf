# Etapa 7 — Compute Pool para processamento Flink SQL.
#
# Criado do zero pelo Terraform, sem importar recursos da V1.
# Utiliza o Environment gerenciado pela Foundation da V2.
#
# max_cfu limita a capacidade, nao reserva 10 CFUs continuamente.
# default_pool=false evita habilitar um pool padrao da organizacao.

resource "confluent_flink_compute_pool" "payment_fraud" {
  display_name = "payment-fraud-v2"
  cloud        = "AWS"
  region       = "us-east-1"
  max_cfu      = 10
  default_pool = false

  environment {
    id = confluent_environment.challenge.id
  }

  lifecycle {
    prevent_destroy = true
  }
}
