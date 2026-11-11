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

  # A protecao contra exclusao durante a execucao e feita pelos gates
  # testados: review_plan e os scripts de etapa rejeitam qualquer delete,
  # e cdc_stage_flags mantem a flag ativa enquanto o recurso esta no State.
  # Somente lab.py teardown (confirmacao DESTROY PIPELINE) remove a politica,
  # permitindo teardown verificavel sem terraform state rm.
  lifecycle {
    prevent_destroy = false
  }
}
