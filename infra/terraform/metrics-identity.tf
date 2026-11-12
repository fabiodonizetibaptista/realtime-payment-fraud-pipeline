# Etapa 13 — Identidade somente leitura para a Metrics API.
#
# A Metrics API exige uma Cloud API key. Em vez de reutilizar a chave
# administrativa do Terraform, uma service account dedicada recebe apenas
# MetricsViewer na organizacao. Gerenciada aqui para que o teardown a
# remova junto com o restante (na run-20261111 ela foi criada e removida
# manualmente pela CLI, e a criacao manual falhou uma vez).

variable "enable_metrics_viewer" {
  description = "Cria a identidade somente leitura da Metrics API (sem custo)."
  type        = bool
  default     = true
}

resource "confluent_service_account" "metrics_viewer" {
  count = var.enable_metrics_viewer ? 1 : 0

  display_name = "desafio-metrics"
  description  = "Leitura da Metrics API (MetricsViewer)"
}

resource "confluent_role_binding" "metrics_viewer" {
  count = var.enable_metrics_viewer ? 1 : 0

  principal   = "User:${confluent_service_account.metrics_viewer[0].id}"
  role_name   = "MetricsViewer"
  crn_pattern = data.confluent_organization.current.resource_name
}

# Sem managed_resource: Cloud API key, exigida pela Metrics API.
resource "confluent_api_key" "metrics_viewer" {
  count = var.enable_metrics_viewer ? 1 : 0

  display_name = "desafio-metrics-cloud"
  description  = "Cloud API key somente leitura da Metrics API"

  owner {
    id          = confluent_service_account.metrics_viewer[0].id
    api_version = confluent_service_account.metrics_viewer[0].api_version
    kind        = confluent_service_account.metrics_viewer[0].kind
  }

  depends_on = [confluent_role_binding.metrics_viewer]
}

output "metrics_api_key_id" {
  description = "ID da Cloud API key de metricas (nao e segredo)."
  value       = try(confluent_api_key.metrics_viewer[0].id, null)
}

output "metrics_api_key_secret" {
  description = "Segredo da Cloud API key de metricas; lido em memoria pelo coletor."
  value       = try(confluent_api_key.metrics_viewer[0].secret, null)
  sensitive   = true
}
