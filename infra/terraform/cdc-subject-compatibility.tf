# Etapa 6 — Politica explicita de compatibilidade do contrato testado.
#
# Mantemos a configuracao global intacta.
# O provider Confluent ja fornece as credenciais do Schema Registry.
#
# Este recurso gerencia a politica, nao registra novas versoes Avro.

resource "confluent_subject_config" "transactions_value" {
  count = var.enable_subject_compatibility ? 1 : 0

  subject_name        = "payments.public.transactions-value"
  compatibility_level = "BACKWARD"

  lifecycle {
    prevent_destroy = true
  }
}
