# Etapa 6 - Contratos Avro gerados pelo CDC.
# O Debezium registra os schemas no Schema Registry.
# Terraform preserva os objetos remotos existentes.

# Os schemas CDC sao registrados pelo conector Debezium.
#
# Os arquivos .avsc permanecem versionados como contratos
# de referencia, mas nao sao registrados pelo Terraform.
#
# Migracao segura:
# caso existam instancias confluent_schema.cdc no State,
# o Terraform deixara de gerencia-las sem excluir os
# subjects existentes no Schema Registry.
#
# IMPORTANTE: revisar o plano antes de aplicar esta migracao.
removed {
  from = confluent_schema.cdc

  lifecycle {
    destroy = false
  }
}
