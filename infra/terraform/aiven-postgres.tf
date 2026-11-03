# PostgreSQL gratuito, criado do zero pela V2.
# O projeto Aiven ja existe e nao sera recriado.
#
# Nao fixamos cloud_name: o plano Free usa uma
# regiao elegivel selecionada pela Aiven.
resource "aiven_pg" "payments" {
  project      = "fabiodonizetibaptista-1c3d"
  service_name = "pg-payment-fraud-lab"
  plan         = "free-1-1gb"
}

# Informacoes nao secretas utilizadas pelos proximos
# itens da Etapa 2.
output "aiven_pg_service_name" {
  value = aiven_pg.payments.service_name
}

output "aiven_pg_host" {
  value = aiven_pg.payments.service_host
}

output "aiven_pg_port" {
  value = aiven_pg.payments.service_port
}
