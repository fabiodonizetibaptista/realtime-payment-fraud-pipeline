# Etapa 6 — Contratos CDC existentes no Schema Registry.
#
# Estes subjects ja possuem schemas registrados.
# IMPORTANTE: importar os 12 recursos existentes para o State
# antes de permitir qualquer terraform apply.
#
# prevent_destroy protege contra exclusao acidental.
# A politica BACKWARD sera tratada separadamente, sem
# alterar a configuracao global do Schema Registry.

locals {
  cdc_schema_subjects = toset([
    "payments.cdc_internal.heartbeat-key",
    "payments.cdc_internal.heartbeat-value",
    "payments.public.accounts-key",
    "payments.public.accounts-value",
    "payments.public.cards-key",
    "payments.public.cards-value",
    "payments.public.customers-key",
    "payments.public.customers-value",
    "payments.public.merchants-key",
    "payments.public.merchants-value",
    "payments.public.transactions-key",
    "payments.public.transactions-value",
  ])
}

resource "confluent_schema" "cdc" {
  for_each = local.cdc_schema_subjects

  subject_name = each.key
  format       = "AVRO"

  schema = file("${path.module}/../../schemas/registry/${each.key}.avsc")

  lifecycle {
    prevent_destroy = true
  }
}
