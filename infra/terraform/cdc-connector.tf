# Etapa 4 — Conector PostgreSQL CDC gerenciado.
#
# Desabilitado por padrao para evitar custos.
# Nao recria Foundation, PostgreSQL, Service Accounts ou ACLs.
# O ciclo de ativacao/destruicao sera controlado separadamente.

variable "enable_cdc_connector" {
  description = "Habilita temporariamente o conector CDC."
  type        = bool
  default     = false
}

variable "cdc_connector_password" {
  description = "Senha do cdc_user; fornecida via TF_VAR_cdc_connector_password."
  type        = string
  sensitive   = true
  default     = ""
}

resource "confluent_connector" "payments_cdc" {
  count = var.enable_cdc_connector ? 1 : 0

  environment {
    id = confluent_environment.challenge.id
  }

  kafka_cluster {
    id = confluent_kafka_cluster.basic.id
  }

  config_nonsensitive = {
    "name"            = "payments-cdc-aiven"
    "connector.class" = "PostgresCdcSourceV2"

    # Utiliza identidade e permissoes da Foundation V2.
    "kafka.auth.mode"          = "SERVICE_ACCOUNT"
    "kafka.service.account.id" = confluent_service_account.cdc.id

    # Host e porta pertencem ao recurso Aiven da V2.
    "database.hostname" = aiven_pg.payments.service_host
    "database.port"     = tostring(aiven_pg.payments.service_port)
    "database.user"     = "cdc_user"
    "database.dbname"   = "defaultdb"
    "database.sslmode"  = "verify-full"

    # Contrato CDC preservado da V1.
    "topic.prefix"                = "payments"
    "slot.name"                   = "payments_cdc_slot"
    "publication.name"            = "payments_publication"
    "publication.autocreate.mode" = "disabled"

    "table.include.list" = join(",", [
      "public.customers",
      "public.accounts",
      "public.cards",
      "public.merchants",
      "public.transactions",
      "cdc_internal.heartbeat"
    ])

    # Snapshot inicial e captura continua de alteracoes.
    "snapshot.mode"         = "initial"
    "output.data.format"    = "AVRO"
    "output.key.format"     = "AVRO"
    "tasks.max"             = "1"
    "heartbeat.interval.ms" = "60000"
  }

  # Nunca incluir senhas em config_nonsensitive.
  config_sensitive = {
    "database.password"    = var.cdc_connector_password
    "database.sslrootcert" = file("${path.module}/../../.local/aiven-ca.pem")
  }

  lifecycle {
    precondition {
      condition     = length(var.cdc_connector_password) > 0
      error_message = "CDC_CONNECTOR_PASSWORD_REQUIRED"
    }
  }
}
