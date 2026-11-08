variable "enable_kafka_acls" {
  description = "Habilita a criacao das ACLs depois que a API Key administrativa estiver exportada para o ambiente local."
  type        = bool
  default     = false
}

variable "kafka_topic_prefix" {
  description = "Prefixo dos topicos autorizados para producer e consumer."
  type        = string
  default     = "desafio-"

  validation {
    condition     = length(trimspace(var.kafka_topic_prefix)) > 0
    error_message = "kafka_topic_prefix nao pode ser vazio."
  }
}

# Provider credentials for the V2 Foundation. These use TF_VAR_* names so
# they cannot accidentally inherit older V1 KAFKA_API_KEY Codespaces secrets.
variable "foundation_kafka_id" {
  description = "Kafka cluster ID used by the Confluent provider for ACL operations."
  type        = string
  default     = ""
}

variable "foundation_kafka_rest_endpoint" {
  description = "Kafka REST endpoint used by the Confluent provider for ACL operations."
  type        = string
  default     = ""
}

variable "foundation_kafka_api_key" {
  description = "Kafka API Key owned by desafio-iac-admin."
  type        = string
  sensitive   = true
  default     = ""
}

variable "foundation_kafka_api_secret" {
  description = "Kafka API secret owned by desafio-iac-admin."
  type        = string
  sensitive   = true
  default     = ""
}

variable "foundation_schema_registry_id" {
  description = "Schema Registry cluster ID used by the Confluent provider."
  type        = string
  default     = ""
}

variable "foundation_schema_registry_rest_endpoint" {
  description = "Schema Registry REST endpoint used by the Confluent provider."
  type        = string
  default     = ""
}

variable "foundation_schema_registry_api_key" {
  description = "Schema Registry API Key owned by desafio-schema-registry."
  type        = string
  sensitive   = true
  default     = ""
}

variable "foundation_schema_registry_api_secret" {
  description = "Schema Registry API secret owned by desafio-schema-registry."
  type        = string
  sensitive   = true
  default     = ""
}

variable "foundation_environment_id" {
  description = "Environment ID gerado pela Foundation e usado por recursos Confluent das etapas seguintes."
  type        = string
  default     = ""
}

variable "cdc_topic_prefix" {
  description = "Prefixo dos topicos produzidos pelo conector CDC."
  type        = string
  default     = "payments"

  validation {
    condition     = length(trimspace(var.cdc_topic_prefix)) > 0
    error_message = "cdc_topic_prefix nao pode ser vazio."
  }
}


# Ativacao independente das ACLs CDC, respeitando a ordem do checklist.
variable "enable_cdc_acls" {
  description = "Habilita somente as ACLs do conector CDC."
  type        = bool
  default     = false
}

# Projeto Aiven existente, informado pelo operador.
# Nao deve ser criado automaticamente pelo Terraform.
variable "aiven_project" {
  description = "Nome do projeto Aiven que hospedara o PostgreSQL."
  type        = string

  validation {
    condition     = length(trimspace(var.aiven_project)) > 0
    error_message = "aiven_project nao pode ser vazio."
  }
}

# Nome parametrizavel para preservar o recurso existente
# e permitir implantacoes independentes.
variable "aiven_pg_service_name" {
  description = "Nome do servico PostgreSQL no projeto Aiven."
  type        = string

  validation {
    condition     = length(trimspace(var.aiven_pg_service_name)) > 0
    error_message = "aiven_pg_service_name nao pode ser vazio."
  }
}

# Nome do conector CDC, configurado pelo operador.
# Deve ser unico no ambiente Confluent utilizado.
variable "cdc_connector_name" {
  description = "Nome do conector PostgreSQL CDC."
  type        = string
  default     = "payments-cdc"

  validation {
    condition     = length(trimspace(var.cdc_connector_name)) > 0
    error_message = "cdc_connector_name nao pode ser vazio."
  }
}
