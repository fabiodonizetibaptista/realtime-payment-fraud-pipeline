# Marco 4 - Foundation do desafio DIO.
# Nomes, cloud e regiao sao variaveis (variables.tf) com os padroes do desafio.
# Nenhum ID ou endpoint da V1 e reutilizado.

resource "confluent_environment" "challenge" {
  display_name = var.confluent_environment_name

  stream_governance {
    package = "ESSENTIALS"
  }
}

resource "confluent_kafka_cluster" "basic" {
  display_name = var.kafka_cluster_name
  availability = "SINGLE_ZONE"
  cloud        = var.confluent_cloud
  region       = var.confluent_region

  basic {}

  environment {
    id = confluent_environment.challenge.id
  }
}

# O Schema Registry Essentials e associado ao Environment. A instanciacao
# regional acontece com o primeiro cluster Kafka do Environment.
data "confluent_schema_registry_cluster" "essentials" {
  environment {
    id = confluent_environment.challenge.id
  }

  depends_on = [confluent_kafka_cluster.basic]
}

# Identidade administrativa usada exclusivamente para administrar ACLs Kafka.
# CloudClusterAdmin fica restrito ao cluster, sem conceder EnvironmentAdmin.
resource "confluent_service_account" "iac_admin" {
  display_name = "desafio-iac-admin"
  description  = "Identidade tecnica para administrar ACLs do cluster do desafio"
}

resource "confluent_role_binding" "iac_admin_cluster_admin" {
  principal   = "User:${confluent_service_account.iac_admin.id}"
  role_name   = "CloudClusterAdmin"
  crn_pattern = confluent_kafka_cluster.basic.rbac_crn
}

# Identidades de aplicacao separadas, conforme o contrato da entrega.
resource "confluent_service_account" "producer" {
  display_name = "desafio-producer"
  description  = "Identidade de producer para topicos com prefixo desafio-"
}

resource "confluent_service_account" "consumer" {
  display_name = "desafio-consumer"
  description  = "Identidade de consumer para topicos e grupos com prefixo desafio-"
}

# O conector gerenciado autentica usando o ID desta Service Account.
# Nao e necessaria uma API Key Kafka separada para esse modo de autenticacao.
resource "confluent_service_account" "cdc" {
  display_name = "desafio-cdc"
  description  = "Identidade do conector CDC PostgreSQL Debezium"
}

resource "confluent_service_account" "schema_registry" {
  display_name = "desafio-schema-registry"
  description  = "Identidade dedicada a publicacao e gestao dos schemas do desafio"
}

# A chave administrativa e de cluster (Kafka), nao Cloud API.
# A identidade recebe CloudClusterAdmin antes da criacao da chave.
resource "confluent_api_key" "iac_admin_kafka" {
  display_name = "desafio-iac-admin-kafka"
  description  = "Kafka API Key usada pelo Terraform para administrar ACLs"

  owner {
    id          = confluent_service_account.iac_admin.id
    api_version = confluent_service_account.iac_admin.api_version
    kind        = confluent_service_account.iac_admin.kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.basic.id
    api_version = confluent_kafka_cluster.basic.api_version
    kind        = confluent_kafka_cluster.basic.kind

    environment {
      id = confluent_environment.challenge.id
    }
  }

  depends_on = [confluent_role_binding.iac_admin_cluster_admin]
}

resource "confluent_api_key" "producer_kafka" {
  display_name = "desafio-producer-kafka"
  description  = "Kafka API Key owned by desafio-producer"

  owner {
    id          = confluent_service_account.producer.id
    api_version = confluent_service_account.producer.api_version
    kind        = confluent_service_account.producer.kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.basic.id
    api_version = confluent_kafka_cluster.basic.api_version
    kind        = confluent_kafka_cluster.basic.kind

    environment {
      id = confluent_environment.challenge.id
    }
  }
}

resource "confluent_api_key" "consumer_kafka" {
  display_name = "desafio-consumer-kafka"
  description  = "Kafka API Key owned by desafio-consumer"

  owner {
    id          = confluent_service_account.consumer.id
    api_version = confluent_service_account.consumer.api_version
    kind        = confluent_service_account.consumer.kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.basic.id
    api_version = confluent_kafka_cluster.basic.api_version
    kind        = confluent_kafka_cluster.basic.kind

    environment {
      id = confluent_environment.challenge.id
    }
  }
}

# Schema Registry usa RBAC por subject, mesmo com Kafka Basic.
# Read e Write sao separados para evitar ResourceOwner, que tambem permite
# gerenciar permissoes e criar identidades. O desafio precisa registrar, ler
# e validar schemas, nao administrar acessos ou excluir subjects.
resource "confluent_role_binding" "schema_registry_subject_read" {
  principal   = "User:${confluent_service_account.schema_registry.id}"
  role_name   = "DeveloperRead"
  crn_pattern = "${data.confluent_schema_registry_cluster.essentials.resource_name}/subject=*"
}

resource "confluent_role_binding" "schema_registry_subject_write" {
  principal   = "User:${confluent_service_account.schema_registry.id}"
  role_name   = "DeveloperWrite"
  crn_pattern = "${data.confluent_schema_registry_cluster.essentials.resource_name}/subject=*"
}

resource "confluent_api_key" "schema_registry" {
  display_name = "desafio-schema-registry"
  description  = "Schema Registry API Key owned by desafio-schema-registry"

  owner {
    id          = confluent_service_account.schema_registry.id
    api_version = confluent_service_account.schema_registry.api_version
    kind        = confluent_service_account.schema_registry.kind
  }

  managed_resource {
    id          = data.confluent_schema_registry_cluster.essentials.id
    api_version = data.confluent_schema_registry_cluster.essentials.api_version
    kind        = data.confluent_schema_registry_cluster.essentials.kind

    environment {
      id = confluent_environment.challenge.id
    }
  }

  depends_on = [
    confluent_role_binding.schema_registry_subject_read,
    confluent_role_binding.schema_registry_subject_write,
  ]
}
