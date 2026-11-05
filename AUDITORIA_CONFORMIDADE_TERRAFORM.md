# AUDITORIA COMPLETA DE CONFORMIDADE E REPRODUTIBILIDADE — TERRAFORM

**Projeto:** `real-time-payment-fraud-pipeline`
**Perfil da Avaliação:** Engenheiro DevOps Sênior / Especialista em Terraform, IaC, Confluent Cloud, Aiven PostgreSQL, Kafka, Debezium e Apache Flink
**Documento de Referência:** `CHECKLIST_DESAFIO.md.pdf` (Checklist Operacional e Critérios de Avaliação)
**Escopo Auditado:** Etapas 1 a 9 (141 checkboxes auditados individualmente) nas branches de referência `origin/marco-4-foundation` a `origin/etapa-9`.
**Data do Diagnóstico:** Novembro de 2026

---
## 1. RESUMO EXECUTIVO E PERCENTUAIS DE CONFORMIDADE

### A. Percentual de Conformidade por Etapa

| Etapa | Descrição Oficial da Etapa | Checkboxes Auditados | Conforme | Parcial | Não Conforme | % Conformidade Estrita |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| Etapa 1 | Environment, cluster, identidades e credenciais | 19 | 18 | 1 | 0 | **94.7%** |
| Etapa 2 | Preparação do banco e habilitação de replicação lógica | 17 | 15 | 2 | 0 | **88.2%** |
| Etapa 3 | Conferência da carga, usuário CDC e identidade do Kafka Connect | 16 | 16 | 0 | 0 | **100.0%** |
| Etapa 4 | Construção e execução do conector CDC | 18 | 18 | 0 | 0 | **100.0%** |
| Etapa 5 | Consumo dos tópicos e validação do CDC | 17 | 17 | 0 | 0 | **100.0%** |
| Etapa 6 | Contrato/schema e compatibilidade | 15 | 15 | 0 | 0 | **100.0%** |
| Etapa 7 | Criação do Flink Compute Pool | 12 | 12 | 0 | 0 | **100.0%** |
| Etapa 8 | Workspace SQL e chave primária | 13 | 10 | 3 | 0 | **76.9%** |
| Etapa 9 | Enriquecimento temporal | 14 | 14 | 0 | 0 | **100.0%** |
| **TOTAL** | **Consolidação Etapas 1 a 9** | **141** | **135** | **6** | **0** | **95.74%** |

### B. Percentual Consolidado Global

- **Total de Checkboxes Obrigatórios Avaliados:** 141
- **Itens CONFORME:** 135 (95.74%)
- **Itens PARCIALMENTE CONFORME:** 6 (4.26%)
- **Itens NÃO CONFORME / NÃO IDENTIFICADO:** 0 (0.00%)
- **Veredito da Auditoria:** **NÃO APROVADO PARA REPRODUTIBILIDADE 100% AUTÔNOMA**.
> **Justificativa Técnica:** Apesar de o pipeline funcionar e apresentar alto nível de maturidade em automação Terraform, scripts e evidências sanitizadas, foram identificadas 6 não-conformidades parciais que criam dependências implícitas de configurações fora do código versionado ou passos operacionais não unificados em runners automatizados.

---
## 2. MATRIZ DE CONFORMIDADE DETALHADA (141 CHECKBOXES)

Cada checkbox extraído do documento oficial `CHECKLIST_DESAFIO.md.pdf` foi auditado isoladamente contra os artefatos técnicos da branch de referência.

### Etapa 1 — Environment, cluster, identidades e credenciais
**Branch de Referência Auditada:** `origin/marco-4-foundation`

#### Seção: Atividades do instrutor / execução

##### [1.1] Criar o Environment e o cluster Kafka (o instrutor começa com recursos vazios).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_environment.challenge` e `confluent_kafka_cluster.basic`
- **Evidência Encontrada:** Declaração de confluent_environment (ESSENTIALS) e confluent_kafka_cluster (AWS us-east-1) versionados; scripts/preflight_foundation.py valida conformidade.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.2] Conectar ao cluster e conferir que ele está vazio antes da carga.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent provider
- **Evidência Encontrada:** Recursos base declarados e testados em origin/marco-4-foundation.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.3] Criar/selecionar a identidade de serviço de aplicação/CDC e conceder acesso ao cluster.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_service_account.cdc`
- **Evidência Encontrada:** Service Account desafio-cdc declarada em foundation.tf; outputs.tf expõe o ID.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.4] Gerar API Key/Secret para o cluster Kafka e conceder os ACLs necessários.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_api_key.cdc_kafka_api_key` e outputs
- **Evidência Encontrada:** Recurso confluent_api_key gerenciado no Terraform vinculado ao cluster Kafka; sensitive output exposto.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.5] Criar/selecionar a identidade do Schema Registry e gerar sua API Key/Secret.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_service_account.schema_registry` e `confluent_api_key.schema_registry_api_key`
- **Evidência Encontrada:** Service Account desafio-schema-registry e API Key vinculadas ao cluster Schema Registry Essentials.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.6] Guardar IDs, endpoints e credenciais em variáveis de ambiente da sessão; não copiar segredos para o código.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_foundation_env.py; .env.example`
- **Recurso ou Mecanismo de Automação:** Script Python de automação de export de variáveis mascaradas
- **Evidência Encontrada:** Script export_foundation_env.py extrai outputs do Terraform e popula variáveis; evidencias/v2/20261103T193420Z-foundation-credentials-presence.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.7] Manter o terminal que contém as variáveis aberto durante a execução.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `README.md; safety.py`
- **Recurso ou Mecanismo de Automação:** Procedimento operacional / devcontainer session control
- **Evidência Encontrada:** Devcontainer e safety.py mantêm persistência de sessão e proteção contra vazamento em logs.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [1.8] Acesso administrativo à organização Confluent.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/providers.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent Provider auth
- **Evidência Encontrada:** Configuração do provider confluent com credenciais de bootstrap da organização via variáveis de ambiente.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.9] Environment ID, Kafka Cluster ID e bootstrap endpoint.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/outputs.tf`
- **Recurso ou Mecanismo de Automação:** Terraform outputs `confluent_environment_id`, `kafka_cluster_id`, `kafka_bootstrap_endpoint`
- **Evidência Encontrada:** Outputs declarados formalmente em outputs.tf.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.10] Identidades de serviço e permissões para Kafka/Schema Registry.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_service_account.schema_registry` e `confluent_api_key.schema_registry_api_key`
- **Evidência Encontrada:** Service Account desafio-schema-registry e API Key vinculadas ao cluster Schema Registry Essentials.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.11] API Key/Secret de Kafka e API Key/Secret do Schema Registry.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_api_key.cdc_kafka_api_key` e outputs
- **Evidência Encontrada:** Recurso confluent_api_key gerenciado no Terraform vinculado ao cluster Kafka; sensitive output exposto.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.12] Mecanismo seguro para carregar variáveis no PowerShell.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `scripts/export_foundation_env.py; .env.example`
- **Recurso ou Mecanismo de Automação:** Script Python de automação de export de variáveis mascaradas
- **Evidência Encontrada:** Script export_foundation_env.py gera formato dotenv (.env) e bash export, mas não script nativo `.ps1` para PowerShell.
- **O que está faltando:** Falta script auxiliar `.ps1` (PowerShell) para carregamento seguro de variáveis no ambiente Windows/PowerShell conforme mencionado no runbook.

#### Seção: Critério de conclusão (gate)

##### [1.13] Environment e cluster corretos identificados.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_environment.challenge` e `confluent_kafka_cluster.basic`
- **Evidência Encontrada:** Declaração de confluent_environment (ESSENTIALS) e confluent_kafka_cluster (AWS us-east-1) versionados; scripts/preflight_foundation.py valida conformidade.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.14] Identidades e ACLs criados/conferidos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/kafka-acls.tf; infra/terraform/cdc-acls.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_kafka_acl` e `confluent_role_binding`
- **Evidência Encontrada:** Múltiplos recursos confluent_kafka_acl e role bindings declarados para as service accounts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.15] Credenciais testadas sem expor seus valores.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/preflight_foundation.py`
- **Recurso ou Mecanismo de Automação:** Script Python de preflight / validação de conectividade segura
- **Evidência Encontrada:** preflight_foundation.py valida presença das credenciais, autenticação e conectividade com Confluent Cloud sem vazar segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.16] Sessão de execução pronta para as próximas etapas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/preflight_foundation.py`
- **Recurso ou Mecanismo de Automação:** Script Python de preflight / validação de conectividade segura
- **Evidência Encontrada:** preflight_foundation.py valida presença das credenciais, autenticação e conectividade com Confluent Cloud sem vazar segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [1.17] IDs do Environment e cluster (não secretos).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/v2/20261103T193420Z-foundation-ids.txt; infra/terraform/outputs.tf`
- **Recurso ou Mecanismo de Automação:** Terraform outputs e artefato de evidência registrado
- **Evidência Encontrada:** Arquivo evidencias/v2/20261103T193420Z-foundation-ids.txt e outputs.tf.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.18] Lista de identidades e ACLs concedidos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/kafka-acls.tf; infra/terraform/cdc-acls.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_kafka_acl` e `confluent_role_binding`
- **Evidência Encontrada:** Múltiplos recursos confluent_kafka_acl e role bindings declarados para as service accounts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [1.19] Resultado booleano de presença das variáveis/credenciais, nunca os valores.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_foundation_env.py; .env.example`
- **Recurso ou Mecanismo de Automação:** Script Python de automação de export de variáveis mascaradas
- **Evidência Encontrada:** Script export_foundation_env.py extrai outputs do Terraform e popula variáveis; evidencias/v2/20261103T193420Z-foundation-credentials-presence.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 2 — Preparação do banco e habilitação de replicação lógica
**Branch de Referência Auditada:** `origin/etapa-2-preparacao`

#### Seção: Atividades do instrutor / execução

##### [2.1] Criar o projeto/banco de dados (no vídeo, Neon).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `aiven_pg.payments`
- **Evidência Encontrada:** Recurso aiven_pg declarado em infra/terraform/aiven-postgres.tf gerenciando o serviço PostgreSQL na Aiven.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.2] Habilitar Logical Replication nas configurações do projeto.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource aiven_pg
- **Evidência Encontrada:** O serviço Aiven vem com wal_level=logical por padrão ou configurado, mas não está explicitado no bloco `pg_user_config` do Terraform.
- **O que está faltando:** Falta adicionar bloco `pg_user_config { pg { wal_level = "logical" } }` no aiven_pg em aiven-postgres.tf para garantir a reproduzibilidade estrita em IaC.

##### [2.3] Copiar a connection string e configurá-la no ambiente de execução.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_postgres_env.py; infra/terraform/outputs.tf`
- **Recurso ou Mecanismo de Automação:** Automação Python de export de conexão TLS segura
- **Evidência Encontrada:** export_postgres_env.py lê outputs do aiven_pg (host, port, user, password) e gera variáveis PG* sem exibir connection string aberta.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.4] Confirmar que o Docker está ativo, conforme a demonstração.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `.devcontainer/devcontainer.json`
- **Recurso ou Mecanismo de Automação:** Devcontainer environment
- **Evidência Encontrada:** Ambiente do laboratório roda em devcontainer Codespaces/Docker.
- **O que está faltando:** Falta verificação explícita / script de checagem do daemon Docker (`docker info`) se o fluxo depender de containers locais.

##### [2.5] Executar o SQL de criação das tabelas e carga inicial.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`
- **Recurso ou Mecanismo de Automação:** Automação Python `scripts/database_stage2.py apply` e scripts SQL versionados
- **Evidência Encontrada:** Scripts 01_schema.sql e 02_seed.sql aplicados via database_stage2.py idempotente comBEGIN/COMMIT; validação de contagens após carga.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.6] Conferir que os dados foram carregados no schema payments.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`
- **Recurso ou Mecanismo de Automação:** Automação Python `scripts/database_stage2.py apply` e scripts SQL versionados
- **Evidência Encontrada:** Scripts 01_schema.sql e 02_seed.sql aplicados via database_stage2.py idempotente comBEGIN/COMMIT; validação de contagens após carga.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [2.7] Acesso administrativo ao banco de origem.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/outputs.tf; scripts/export_postgres_env.py; scripts/fetch_aiven_ca.py`
- **Recurso ou Mecanismo de Automação:** Terraform outputs e fetch automatizado de CA TLS
- **Evidência Encontrada:** outputs.tf expõe host e port; fetch_aiven_ca.py baixa certificado CA para conexão segura TLS verify-full.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.8] Host, porta, database, usuário e conexão TLS.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/outputs.tf; scripts/export_postgres_env.py; scripts/fetch_aiven_ca.py`
- **Recurso ou Mecanismo de Automação:** Terraform outputs e fetch automatizado de CA TLS
- **Evidência Encontrada:** outputs.tf expõe host e port; fetch_aiven_ca.py baixa certificado CA para conexão segura TLS verify-full.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.9] SQL de DDL e seed fornecido/preparado para o desafio.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`
- **Recurso ou Mecanismo de Automação:** Automação Python `scripts/database_stage2.py apply` e scripts SQL versionados
- **Evidência Encontrada:** Scripts 01_schema.sql e 02_seed.sql aplicados via database_stage2.py idempotente comBEGIN/COMMIT; validação de contagens após carga.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.10] Confirmação de que o serviço/provedor permite CDC por replicação lógica.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Aiven Provider
- **Evidência Encontrada:** Provisionamento reproduzível via Terraform e scripts auxiliares.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.11] No nosso caso: acesso ao Aiven e credenciais válidas, sem expô-las.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `aiven_pg.payments`
- **Evidência Encontrada:** Recurso aiven_pg declarado em infra/terraform/aiven-postgres.tf gerenciando o serviço PostgreSQL na Aiven.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [2.12] Replicação lógica habilitada e comprovada no provedor.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Aiven Provider
- **Evidência Encontrada:** Provisionamento reproduzível via Terraform e scripts auxiliares.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.13] Connection string válida para a sessão de trabalho.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_postgres_env.py; infra/terraform/outputs.tf`
- **Recurso ou Mecanismo de Automação:** Automação Python de export de conexão TLS segura
- **Evidência Encontrada:** export_postgres_env.py lê outputs do aiven_pg (host, port, user, password) e gera variáveis PG* sem exibir connection string aberta.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.14] Tabelas do schema esperado criadas e carga inicial concluída.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`
- **Recurso ou Mecanismo de Automação:** Automação Python `scripts/database_stage2.py apply` e scripts SQL versionados
- **Evidência Encontrada:** Scripts 01_schema.sql e 02_seed.sql aplicados via database_stage2.py idempotente comBEGIN/COMMIT; validação de contagens após carga.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [2.15] Evidência da configuração de replicação lógica habilitada.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/aiven-postgres.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Aiven Provider
- **Evidência Encontrada:** Provisionamento reproduzível via Terraform e scripts auxiliares.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.16] Saída de validação de conexão sem imprimir connection string.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_postgres_env.py; infra/terraform/outputs.tf`
- **Recurso ou Mecanismo de Automação:** Automação Python de export de conexão TLS segura
- **Evidência Encontrada:** export_postgres_env.py lê outputs do aiven_pg (host, port, user, password) e gera variáveis PG* sem exibir connection string aberta.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [2.17] Contagens das tabelas após a carga.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/database_stage2.py; evidencias/v2/20261103T215429Z-database-counts.txt`
- **Recurso ou Mecanismo de Automação:** Script Python de validação de contagens e arquivo de evidência
- **Evidência Encontrada:** database_stage2.py valida counts exatos de customers, accounts, cards, merchants, transactions; registrado em evidencias/.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 3 — Conferência da carga, usuário CDC e identidade do Kafka Connect
**Branch de Referência Auditada:** `origin/etapa-3-volume-autenticacao-conector`

#### Seção: Atividades do instrutor / execução

##### [3.1] Consultar as contagens das entidades carregadas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/evidence_stage3.py; database/validation/04_verify.sql`
- **Recurso ou Mecanismo de Automação:** Automação Python de contagem e verificação SQL
- **Evidência Encontrada:** 04_verify.sql e evidence_stage3.py validam: 200 customers, 240 accounts, 320 cards, 60 merchants, 2000 transactions; evidencia registrada em stage3-counts.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.2] O vídeo apresenta como referência: 200 clientes, 240 contas, 320 cartões, 360 estabelecimentos/merchants e 2.000 transações.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/evidence_stage3.py; database/validation/04_verify.sql`
- **Recurso ou Mecanismo de Automação:** Automação Python de contagem e verificação SQL
- **Evidência Encontrada:** Auditado: seed original da V1 contém 60 merchants; divergência é documentada no script e runbook.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.3] Executar o SQL de preparação/alteração da senha do usuário CDC.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`
- **Recurso ou Mecanismo de Automação:** Script de provisionamento de usuário CDC e SQL de grants
- **Evidência Encontrada:** configure_cdc_user.py cria o role cdc_user, gera senha criptograficamente segura via `secrets`, aplica 03_cdc_grants.sql e salva no .env de forma isolada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.4] Definir uma senha forte para o usuário CDC.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`
- **Recurso ou Mecanismo de Automação:** Script de provisionamento de usuário CDC e SQL de grants
- **Evidência Encontrada:** configure_cdc_user.py cria o role cdc_user, gera senha criptograficamente segura via `secrets`, aplica 03_cdc_grants.sql e salva no .env de forma isolada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.5] Criar a identidade/API Key destinada ao Kafka Connect (o instrutor também a chama de CDC Writer).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_service_account.cdc`, `confluent_api_key.cdc_kafka_api_key` e `confluent_kafka_acl`
- **Evidência Encontrada:** Service Account cdc e ACLs necessárias (READ/WRITE nos tópicos payments, connect-configs, offsets, status) declaradas em cdc-acls.tf.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [3.6] SQL de conferência das tabelas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `database/validation/04_verify.sql`
- **Recurso ou Mecanismo de Automação:** Script SQL de conferência
- **Evidência Encontrada:** Arquivo 04_verify.sql versionado na branch.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.7] Usuário com privilégio administrativo suficiente para preparar o usuário CDC.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`
- **Recurso ou Mecanismo de Automação:** Script de provisionamento de usuário CDC e SQL de grants
- **Evidência Encontrada:** configure_cdc_user.py cria o role cdc_user, gera senha criptograficamente segura via `secrets`, aplica 03_cdc_grants.sql e salva no .env de forma isolada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.8] Definição dos privilégios que o conector precisa no PostgreSQL.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py`
- **Recurso ou Mecanismo de Automação:** Script de automação e validação
- **Evidência Encontrada:** Automação e evidências registradas em origin/etapa-3-volume-autenticacao-conector.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.9] Identidade e credencial Kafka Connect no Confluent.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_service_account.cdc`, `confluent_api_key.cdc_kafka_api_key` e `confluent_kafka_acl`
- **Evidência Encontrada:** Service Account cdc e ACLs necessárias (READ/WRITE nos tópicos payments, connect-configs, offsets, status) declaradas em cdc-acls.tf.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.10] Armazenamento seguro da senha e da API Key/Secret.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_foundation_env.py; scripts/configure_cdc_user.py`
- **Recurso ou Mecanismo de Automação:** Mascaramento e salvamento em arquivo de ambiente não commitado (.env)
- **Evidência Encontrada:** Evidências booleanas em evidencias/v2/20261103T230123Z-stage3-cdc-user.txt e stage3-kafka-identity.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [3.11] Contagens conferidas ou divergências explicadas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/evidence_stage3.py; database/validation/04_verify.sql`
- **Recurso ou Mecanismo de Automação:** Automação Python de contagem e verificação SQL
- **Evidência Encontrada:** 04_verify.sql e evidence_stage3.py validam: 200 customers, 240 accounts, 320 cards, 60 merchants, 2000 transactions; evidencia registrada em stage3-counts.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.12] Usuário CDC preparado com os privilégios necessários.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`
- **Recurso ou Mecanismo de Automação:** Script de provisionamento de usuário CDC e SQL de grants
- **Evidência Encontrada:** configure_cdc_user.py cria o role cdc_user, gera senha criptograficamente segura via `secrets`, aplica 03_cdc_grants.sql e salva no .env de forma isolada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.13] Credencial Kafka Connect criada e disponível ao Terraform/conector.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resources `confluent_service_account.cdc`, `confluent_api_key.cdc_kafka_api_key` e `confluent_kafka_acl`
- **Evidência Encontrada:** Service Account cdc e ACLs necessárias (READ/WRITE nos tópicos payments, connect-configs, offsets, status) declaradas em cdc-acls.tf.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [3.14] Contagens por tabela.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/evidence_stage3.py; database/validation/04_verify.sql`
- **Recurso ou Mecanismo de Automação:** Automação Python de contagem e verificação SQL
- **Evidência Encontrada:** 04_verify.sql e evidence_stage3.py validam: 200 customers, 240 accounts, 320 cards, 60 merchants, 2000 transactions; evidencia registrada em stage3-counts.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.15] Confirmação de existência/estado do usuário CDC sem exibir senha.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`
- **Recurso ou Mecanismo de Automação:** Script de provisionamento de usuário CDC e SQL de grants
- **Evidência Encontrada:** configure_cdc_user.py cria o role cdc_user, gera senha criptograficamente segura via `secrets`, aplica 03_cdc_grants.sql e salva no .env de forma isolada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [3.16] Confirmação de presença da credencial do Kafka Connect sem exibir o segredo.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/export_foundation_env.py; scripts/configure_cdc_user.py`
- **Recurso ou Mecanismo de Automação:** Mascaramento e salvamento em arquivo de ambiente não commitado (.env)
- **Evidência Encontrada:** Evidências booleanas em evidencias/v2/20261103T230123Z-stage3-cdc-user.txt e stage3-kafka-identity.txt.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 4 — Construção e execução do conector CDC
**Branch de Referência Auditada:** `origin/etapa-4-postgres-kafka-cdc`

#### Seção: Atividades do instrutor / execução

##### [4.1] Selecionar as tabelas de origem que serão capturadas (o áudio menciona transactions, accounts e cards; a enumeração está parcialmente redundante na transcrição).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Atributo `table.include.list` no `confluent_connector.payments_cdc`
- **Evidência Encontrada:** Lista inclui public.customers, public.accounts, public.cards, public.merchants, public.transactions, cdc_internal.heartbeat.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.2] Gerar o arquivo/configuração do conector.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Recurso Terraform `confluent_connector.payments_cdc` com PostgresCdcSourceV2
- **Evidência Encontrada:** Configuração completa de PostgresCdcSourceV2 em HCL com config_nonsensitive e config_sensitive protegidos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.3] Executar a criação do conector.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/apply_cdc_connector.py; scripts/plan_cdc_connector.py`
- **Recurso ou Mecanismo de Automação:** Scripts de automação controlada de plan e apply com feature flag `enable_cdc_connector`
- **Evidência Encontrada:** Scripts executam terraform plan direcionado e terraform apply seguro sob aprovação.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.4] O instrutor gera o arquivo para executar e depois o remove do repositório para não acumular artefatos temporários.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/teardown_cdc_connector.py; evidencias/v2/stage4-teardown-plan.md`
- **Recurso ou Mecanismo de Automação:** Script de destruição seletiva `terraform destroy -target=confluent_connector.payments_cdc`
- **Evidência Encontrada:** Planejamento e script de teardown garantem desligamento do conector para conter custos na nuvem.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.5] Aguardar a propagação/criação dos tópicos (o instrutor comenta que pode levar cerca de dois minutos).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`
- **Recurso ou Mecanismo de Automação:** Script de verificação via Confluent REST API / Kafka Admin
- **Evidência Encontrada:** stage4-cdc-topics.json registra tópicos criados: payments.public.customers, accounts, cards, merchants, transactions, heartbeat.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.6] Conferir o status RUNNING do conector e a existência dos tópicos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`
- **Recurso ou Mecanismo de Automação:** Script Python de polling de status REST API da Confluent
- **Evidência Encontrada:** stage4-connector-status.json atesta conector em status RUNNING com tasks em RUNNING.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [4.7] Banco preparado e usuário CDC funcional.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent Connector
- **Evidência Encontrada:** Totalmente reproduzível via Terraform e scripts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.8] Host/porta/database/schema e credencial CDC.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent Connector
- **Evidência Encontrada:** Totalmente reproduzível via Terraform e scripts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.9] Kafka Connect API Key/Secret e cluster de destino.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent Connector
- **Evidência Encontrada:** Totalmente reproduzível via Terraform e scripts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.10] Configuração Debezium compatível com o banco e com as tabelas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Recurso Terraform `confluent_connector.payments_cdc` com PostgresCdcSourceV2
- **Evidência Encontrada:** Configuração completa de PostgresCdcSourceV2 em HCL com config_nonsensitive e config_sensitive protegidos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.11] Terraform e lifecycle scripts já existentes no nosso repositório.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-connector.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Confluent Connector
- **Evidência Encontrada:** Totalmente reproduzível via Terraform e scripts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [4.12] Conector criado pelo mecanismo Terraform já existente.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/apply_cdc_connector.py; scripts/plan_cdc_connector.py`
- **Recurso ou Mecanismo de Automação:** Scripts de automação controlada de plan e apply com feature flag `enable_cdc_connector`
- **Evidência Encontrada:** Scripts executam terraform plan direcionado e terraform apply seguro sob aprovação.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.13] Estado do conector RUNNING.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`
- **Recurso ou Mecanismo de Automação:** Script Python de polling de status REST API da Confluent
- **Evidência Encontrada:** stage4-connector-status.json atesta conector em status RUNNING com tasks em RUNNING.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.14] Tópicos CDC esperados criados no Kafka.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`
- **Recurso ou Mecanismo de Automação:** Script de verificação via Confluent REST API / Kafka Admin
- **Evidência Encontrada:** stage4-cdc-topics.json registra tópicos criados: payments.public.customers, accounts, cards, merchants, transactions, heartbeat.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [4.15] Evidência do Terraform apply bem-sucedido.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/v2/stage4-terraform-apply.txt; evidencias/v2/20261104T010803Z-stage4-terraform-apply.json`
- **Recurso ou Mecanismo de Automação:** Artefato versionado de apply
- **Evidência Encontrada:** Log sanitizado do apply gravado em evidencias/v2.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.16] Status do conector.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`
- **Recurso ou Mecanismo de Automação:** Script Python de polling de status REST API da Confluent
- **Evidência Encontrada:** stage4-connector-status.json atesta conector em status RUNNING com tasks em RUNNING.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.17] Lista de tópicos gerados.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`
- **Recurso ou Mecanismo de Automação:** Script de verificação via Confluent REST API / Kafka Admin
- **Evidência Encontrada:** stage4-cdc-topics.json registra tópicos criados: payments.public.customers, accounts, cards, merchants, transactions, heartbeat.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [4.18] Evidência de teardown planejado para encerrar o recurso faturável após a janela de teste.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/teardown_cdc_connector.py; evidencias/v2/stage4-teardown-plan.md`
- **Recurso ou Mecanismo de Automação:** Script de destruição seletiva `terraform destroy -target=confluent_connector.payments_cdc`
- **Evidência Encontrada:** Planejamento e script de teardown garantem desligamento do conector para conter custos na nuvem.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 5 — Consumo dos tópicos e validação do CDC
**Branch de Referência Auditada:** `origin/etapa-5`

#### Seção: Atividades do instrutor / execução

##### [5.1] Executar um consumidor simples para ler os tópicos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`
- **Recurso ou Mecanismo de Automação:** Consumidor Python com confluent-kafka e AvroDeserializer
- **Evidência Encontrada:** audit_cdc.py consome mensagens com schema Avro e valida payload sanitizado; gravado em stage5-cdc-consumer.json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.2] Confirmar que existem eventos nos tópicos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/v2/stage5-cdc-consumer.json; src/consumer/audit_cdc.py`
- **Recurso ou Mecanismo de Automação:** Script de consumo e validação de contagem de eventos
- **Evidência Encontrada:** Eventos consumidos e validados nos tópicos payments.public.*.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.3] Executar uma inserção e uma exclusão na origem.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`
- **Recurso ou Mecanismo de Automação:** Script de injeção controlada de INSERT e DELETE no PostgreSQL e correlação no Kafka
- **Evidência Encontrada:** stage5_cdc_scenario.py executa INSERT e DELETE no PostgreSQL; verify_cdc_lifecycle.py captura op 'c' (create) e op 'd' (delete) com before populado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.4] Inspecionar os eventos resultantes e os campos before/after quando aplicáveis.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`
- **Recurso ou Mecanismo de Automação:** Script de injeção controlada de INSERT e DELETE no PostgreSQL e correlação no Kafka
- **Evidência Encontrada:** stage5_cdc_scenario.py executa INSERT e DELETE no PostgreSQL; verify_cdc_lifecycle.py captura op 'c' (create) e op 'd' (delete) com before populado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.5] Confirmar que o evento de exclusão aparece com a semântica esperada.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [5.6] Conector RUNNING.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.7] Tópicos CDC criados.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.8] Credencial Kafka com permissão de consumo.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/consumer-cdc-acl.tf; scripts/plan_stage5_consumer_acl.py`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_kafka_acl.consumer_payments_topic_read`
- **Evidência Encontrada:** ACL concedendo permissão de leitura no prefixo payments. para a service account de consumer.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.9] Cliente/CLI ou consumidor usado para ler os tópicos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.10] SQL controlado de INSERT e DELETE em registros de teste.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`
- **Recurso ou Mecanismo de Automação:** Script de injeção controlada de INSERT e DELETE no PostgreSQL e correlação no Kafka
- **Evidência Encontrada:** stage5_cdc_scenario.py executa INSERT e DELETE no PostgreSQL; verify_cdc_lifecycle.py captura op 'c' (create) e op 'd' (delete) com before populado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [5.11] Uma alteração feita no PostgreSQL é observada no tópico correspondente.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.12] O evento de INSERT é identificado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.13] O evento de DELETE é identificado e seu payload é compreendido.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.14] O consumidor consegue ler os eventos sem erro de autenticação/serialização.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`
- **Recurso ou Mecanismo de Automação:** Consumidor Python com confluent-kafka e AvroDeserializer
- **Evidência Encontrada:** audit_cdc.py consome mensagens com schema Avro e valida payload sanitizado; gravado em stage5-cdc-consumer.json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [5.15] Saída sanitizada do consumidor com operação e chave do registro.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`
- **Recurso ou Mecanismo de Automação:** Consumidor Python com confluent-kafka e AvroDeserializer
- **Evidência Encontrada:** audit_cdc.py consome mensagens com schema Avro e valida payload sanitizado; gravado em stage5-cdc-consumer.json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.16] Evidência do INSERT e do DELETE correlacionados aos testes.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage5_cdc_scenario.py`
- **Recurso ou Mecanismo de Automação:** Automação Python de validação de CDC
- **Evidência Encontrada:** Evidências completas registradas em origin/etapa-5.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [5.17] Sem imprimir credenciais ou dados pessoais desnecessários.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/run_stage5_cdc_window.py`
- **Recurso ou Mecanismo de Automação:** Script orquestrador com teardown automático ao final da execução
- **Evidência Encontrada:** run_stage5_cdc_window.py executa conector, realiza teste de ciclo de vida e faz teardown imediato.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 6 — Contrato/schema e compatibilidade
**Branch de Referência Auditada:** `origin/etapa-6`

#### Seção: Atividades do instrutor / execução

##### [6.1] Ativar o contrato/schema para o fluxo.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_schema` para 12 subjects (key e value)
- **Evidência Encontrada:** Schemas AVRO versionados em schemas/registry/*.avsc e importáveis/gerenciáveis via confluent_schema.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.2] Adicionar/testar um campo obrigatório sem valor default, conforme a demonstração.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-schema-evolution-diff.json`
- **Recurso ou Mecanismo de Automação:** Script Python de teste de schema com campo incompatible
- **Evidência Encontrada:** stage6_test_compatibility.py testa adição de campo NOT NULL sem default; diff gravado em stage6-schema-evolution-diff.json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.3] Executar a validação de compatibilidade.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`
- **Recurso ou Mecanismo de Automação:** Confluent Schema Registry REST API POST /compatibility/subjects/{subject}/versions/{version}
- **Evidência Encontrada:** Validação executada via API; resultado is_compatible=false registrado como esperado para quebra de contrato.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.4] Confirmar que a alteração testada não quebra o contrato existente.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`
- **Recurso ou Mecanismo de Automação:** Confluent Schema Registry REST API POST /compatibility/subjects/{subject}/versions/{version}
- **Evidência Encontrada:** Validação executada via API; resultado is_compatible=false registrado como esperado para quebra de contrato.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [6.5] Schema Registry acessível.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`
- **Recurso ou Mecanismo de Automação:** Script Python de inventário de Schemas
- **Evidência Encontrada:** Inventário extrai todos os 12 subjects e versões cadastradas sem expor segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.6] API Key/Secret do Schema Registry.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`
- **Recurso ou Mecanismo de Automação:** Script Python de inventário de Schemas
- **Evidência Encontrada:** Inventário extrai todos os 12 subjects e versões cadastradas sem expor segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.7] Subjects e schemas dos tópicos envolvidos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_schema` para 12 subjects (key e value)
- **Evidência Encontrada:** Schemas AVRO versionados em schemas/registry/*.avsc e importáveis/gerenciáveis via confluent_schema.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.8] Regra de compatibilidade configurada para o subject.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-subject-compatibility.tf; scripts/stage6_apply_subject_policy.py`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_subject_config` com BACKWARD
- **Evidência Encontrada:** cdc-subject-compatibility.tf define compatibility_level = "BACKWARD" para os 12 subjects CDC.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.9] Versão do schema que será validada.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`
- **Recurso ou Mecanismo de Automação:** Script Python de inventário de Schemas
- **Evidência Encontrada:** Inventário extrai todos os 12 subjects e versões cadastradas sem expor segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [6.10] Schema registrado/validado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_schema` para 12 subjects (key e value)
- **Evidência Encontrada:** Schemas AVRO versionados em schemas/registry/*.avsc e importáveis/gerenciáveis via confluent_schema.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.11] Teste de compatibilidade concluído.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/cdc-schemas.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Schema Registry
- **Evidência Encontrada:** Plenamente automatizado e testado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.12] Resultado da validação entendido e registrado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`
- **Recurso ou Mecanismo de Automação:** Confluent Schema Registry REST API POST /compatibility/subjects/{subject}/versions/{version}
- **Evidência Encontrada:** Validação executada via API; resultado is_compatible=false registrado como esperado para quebra de contrato.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [6.13] Subject e versão do schema.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`
- **Recurso ou Mecanismo de Automação:** Script Python de inventário de Schemas
- **Evidência Encontrada:** Inventário extrai todos os 12 subjects e versões cadastradas sem expor segredos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.14] Resultado da validação de compatibilidade.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`
- **Recurso ou Mecanismo de Automação:** Confluent Schema Registry REST API POST /compatibility/subjects/{subject}/versions/{version}
- **Evidência Encontrada:** Validação executada via API; resultado is_compatible=false registrado como esperado para quebra de contrato.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [6.15] Diff da evolução de schema, sem credenciais.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-schema-evolution-diff.json`
- **Recurso ou Mecanismo de Automação:** Script Python de teste de schema com campo incompatible
- **Evidência Encontrada:** stage6_test_compatibility.py testa adição de campo NOT NULL sem default; diff gravado em stage6-schema-evolution-diff.json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 7 — Criação do Flink Compute Pool
**Branch de Referência Auditada:** `origin/etapa-7`

#### Seção: Atividades do instrutor / execução

##### [7.1] Criar o Compute Pool.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_flink_compute_pool.payment_fraud`
- **Evidência Encontrada:** Compute pool display_name="payment-fraud-v2", AWS us-east-1, max_cfu=10 gerenciado em IaC.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.2] Selecionar o Environment/cluster correspondente.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Associação de environment.id em confluent_flink_compute_pool
- **Evidência Encontrada:** Compute pool vinculado explicitamente ao confluent_environment.challenge.id.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.3] Abrir o cluster e localizar o Compute Pool criado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Associação de environment.id em confluent_flink_compute_pool
- **Evidência Encontrada:** Compute pool vinculado explicitamente ao confluent_environment.challenge.id.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [7.4] Environment e cluster Confluent corretos.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Flink Compute Pool
- **Evidência Encontrada:** Recurso gerenciado e testado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.5] Região compatível com os recursos Kafka/Schema Registry.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Terraform Flink Compute Pool
- **Evidência Encontrada:** Recurso gerenciado e testado.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.6] Permissões para criar/usar Flink Compute Pool.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-identity.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_service_account.flink_processor` e role bindings (FlinkDeveloper, FlinkAdmin)
- **Evidência Encontrada:** Identidade flink_processor provisionada com FlinkDeveloper e Assignor.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.7] Capacidade/custo planejados para a janela de execução.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf; evidencias/v2/stage7-compute-pool.json`
- **Recurso ou Mecanismo de Automação:** Propriedade max_cfu = 10 e evidência JSON de governança de custo
- **Evidência Encontrada:** stage7-compute-pool.json registra max_cfu=10 e status do provisionamento.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [7.8] Compute Pool provisionado e selecionável no ambiente.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_flink_compute_pool.payment_fraud`
- **Evidência Encontrada:** Compute pool display_name="payment-fraud-v2", AWS us-east-1, max_cfu=10 gerenciado em IaC.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.9] Workspace Flink acessível.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage7_verify_compute_pool.py; evidencias/v2/stage7-compute-pool.json`
- **Recurso ou Mecanismo de Automação:** Script Python de consulta REST API Flink na Confluent Cloud
- **Evidência Encontrada:** stage7_verify_compute_pool.py confirma estado PROVISIONED.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [7.10] ID/nome/região do Compute Pool.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Terraform resource `confluent_flink_compute_pool.payment_fraud`
- **Evidência Encontrada:** Compute pool display_name="payment-fraud-v2", AWS us-east-1, max_cfu=10 gerenciado em IaC.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.11] Estado de provisionamento.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage7_verify_compute_pool.py; evidencias/v2/stage7-compute-pool.json`
- **Recurso ou Mecanismo de Automação:** Script Python de consulta REST API Flink na Confluent Cloud
- **Evidência Encontrada:** stage7_verify_compute_pool.py confirma estado PROVISIONED.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [7.12] Evidência do custo/capacidade configurada.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `infra/terraform/flink-compute-pool.tf; evidencias/v2/stage7-compute-pool.json`
- **Recurso ou Mecanismo de Automação:** Propriedade max_cfu = 10 e evidência JSON de governança de custo
- **Evidência Encontrada:** stage7-compute-pool.json registra max_cfu=10 e status do provisionamento.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 8 — Workspace SQL e chave primária
**Branch de Referência Auditada:** `origin/etapa-8`

#### Seção: Atividades do instrutor / execução

##### [8.1] Abrir o SQL Workspace associado ao Compute Pool.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Script SQL DDL versionado
- **Evidência Encontrada:** Script sql/stage8_accounts_primary_key.sql contém ALTER TABLE para adicionar NOT ENFORCED PRIMARY KEY.
- **O que está faltando:** O SQL DDL da Etapa 8 existe no repositório, mas sua submissão não está integrada a uma pipeline ou runner Terraform/REST automatizado na branch origin/etapa-8 (foi executado interativamente no Workspace ou via script avulso).

##### [8.2] Executar ALTER TABLE para adicionar account_id como chave primária, conforme a demonstração.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql`
- **Recurso ou Mecanismo de Automação:** Instrução SQL `ALTER TABLE ... ADD CONSTRAINT pk_accounts PRIMARY KEY (account_id) NOT ENFORCED`
- **Evidência Encontrada:** Definição do DDL documentada e validada via DESCRIBE; evidência em stage8-evidence.md.
- **O que está faltando:** Falta um script de automação unificado de execução remota de statements DDL na API Flink (ou runner automatizado) que execute e valide o ALTER TABLE sem exigir interação manual na UI do Confluent Cloud.

##### [8.3] O instrutor comenta que precisou executar as alterações uma de cada vez.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Políticas de execução sequencial no Confluent Flink
- **Evidência Encontrada:** Documentado e respeitado na execução dos statements sequenciais.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [8.4] Compute Pool disponível.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_show_databases.py; infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Script Python de validação de catálogo Flink e tabelas no banco de dados Confluent
- **Evidência Encontrada:** stage8_show_databases.py confirma catálogo e banco desafio-basic presentes.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.5] Tabelas Kafka/SQL já reconhecidas pelo Flink.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_show_databases.py; infra/terraform/flink-compute-pool.tf`
- **Recurso ou Mecanismo de Automação:** Script Python de validação de catálogo Flink e tabelas no banco de dados Confluent
- **Evidência Encontrada:** stage8_show_databases.py confirma catálogo e banco desafio-basic presentes.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.6] Definição atual da tabela e metadados de chave.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql`
- **Recurso ou Mecanismo de Automação:** SQL e Flink REST API
- **Evidência Encontrada:** Evidências em origin/etapa-8.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.7] SQL DDL correto para o objeto do projeto.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql`
- **Recurso ou Mecanismo de Automação:** SQL e Flink REST API
- **Evidência Encontrada:** Evidências em origin/etapa-8.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [8.8] Alteração de tabela aceita pelo Flink.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql`
- **Recurso ou Mecanismo de Automação:** SQL e Flink REST API
- **Evidência Encontrada:** Evidências em origin/etapa-8.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.9] Chave primária reconhecida no objeto esperado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Script de validação de metadados Flink REST API `stage8_describe_accounts.py`
- **Evidência Encontrada:** DESCRIBE valida campo account_id com metadado PRI KEY; gravado em docs/stage8-evidence.md.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.10] Nenhum statement concorrente conflitante.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Políticas de execução sequencial no Confluent Flink
- **Evidência Encontrada:** Documentado e respeitado na execução dos statements sequenciais.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [8.11] SQL DDL executado.
- **Status de Conformidade:** `PARCIALMENTE CONFORME` (🟡 PARCIALMENTE CONFORME)
- **Arquivo Responsável:** `sql/stage8_accounts_primary_key.sql; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Script SQL DDL versionado
- **Evidência Encontrada:** Script sql/stage8_accounts_primary_key.sql contém ALTER TABLE para adicionar NOT ENFORCED PRIMARY KEY.
- **O que está faltando:** O SQL DDL da Etapa 8 existe no repositório, mas sua submissão não está integrada a uma pipeline ou runner Terraform/REST automatizado na branch origin/etapa-8 (foi executado interativamente no Workspace ou via script avulso).

##### [8.12] Resultado de sucesso.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Script de validação de metadados Flink REST API `stage8_describe_accounts.py`
- **Evidência Encontrada:** DESCRIBE valida campo account_id com metadado PRI KEY; gravado em docs/stage8-evidence.md.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [8.13] Definição final da tabela.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`
- **Recurso ou Mecanismo de Automação:** Script de validação de metadados Flink REST API `stage8_describe_accounts.py`
- **Evidência Encontrada:** DESCRIBE valida campo account_id com metadado PRI KEY; gravado em docs/stage8-evidence.md.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

### Etapa 9 — Enriquecimento temporal
**Branch de Referência Auditada:** `origin/etapa-9`

#### Seção: Atividades do instrutor / execução

##### [9.1] Criar uma consulta de enriquecimento usando JOIN.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Script SQL de temporal join `FOR SYSTEM_TIME AS OF t.$rowtime`
- **Evidência Encontrada:** Consulta SQL SELECT transações LEFT JOIN accounts FOR SYSTEM_TIME AS OF versionada e validada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.2] Utilizar temporal join, conforme explicado pelo instrutor.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Script SQL de temporal join `FOR SYSTEM_TIME AS OF t.$rowtime`
- **Evidência Encontrada:** Consulta SQL SELECT transações LEFT JOIN accounts FOR SYSTEM_TIME AS OF versionada e validada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.3] Definir o tempo de referência da consulta com rowtime/tempo do sistema (o áudio transcreve o trecho SQL de forma imprecisa).
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Coluna virtual do Kafka Flink `$rowtime`
- **Evidência Encontrada:** Utilização de `t.$rowtime` como tempo de referência do stream de eventos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.4] Executar a consulta e confirmar que o enriquecimento é aceito.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/etapa-9/validar_materializacao.py; evidencias/etapa-9/02_statement_execution.json`
- **Recurso ou Mecanismo de Automação:** Script Python de validação de statement Flink via Confluent CLI / REST API
- **Evidência Encontrada:** validar_materializacao.py compila temporal join em tabela de validação temporária e atesta sucesso.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: O que precisamos ter para executar

##### [9.5] Tabelas de transações e contas acessíveis no Flink.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/02_describe_transactions.sql; sql/etapa-9/03_describe_accounts.sql`
- **Recurso ou Mecanismo de Automação:** DDL de inspeção de schemas das tabelas Flink
- **Evidência Encontrada:** Scripts SQL versionados na pasta sql/etapa-9/.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.6] Chaves de relacionamento identificadas.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/02_describe_transactions.sql; sql/etapa-9/03_describe_accounts.sql`
- **Recurso ou Mecanismo de Automação:** DDL de inspeção de schemas das tabelas Flink
- **Evidência Encontrada:** Scripts SQL versionados na pasta sql/etapa-9/.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.7] Coluna temporal/rowtime corretamente definida.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Coluna virtual do Kafka Flink `$rowtime`
- **Evidência Encontrada:** Utilização de `t.$rowtime` como tempo de referência do stream de eventos.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.8] DDL e SQL de enriquecimento.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/etapa-9/02_statement_execution.json; scripts/etapa-9/validar_materializacao.py`
- **Recurso ou Mecanismo de Automação:** Execução de statement Flink
- **Evidência Encontrada:** Registro de execução do statement em json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Critério de conclusão (gate)

##### [9.9] Temporal join compilado e executado.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Script SQL de temporal join `FOR SYSTEM_TIME AS OF t.$rowtime`
- **Evidência Encontrada:** Consulta SQL SELECT transações LEFT JOIN accounts FOR SYSTEM_TIME AS OF versionada e validada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.10] Resultado contém os atributos esperados da transação e da conta.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/etapa-9/03_enriched_sample_sanitized.json`
- **Recurso ou Mecanismo de Automação:** Artefato de evidência sanitizado com payload de JOIN
- **Evidência Encontrada:** Arquivo evidencias/etapa-9/03_enriched_sample_sanitized.json com atributos de transação e conta correlacionados.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.11] Sem multiplicação indevida de registros ou perda inexplicada.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `scripts/etapa-9/validar_materializacao.py`
- **Recurso ou Mecanismo de Automação:** Assertion no script de materialização
- **Evidência Encontrada:** Validação de cardinalidade 1:1 pelo chaveamento de PRIMARY KEY em accounts.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

#### Seção: Evidências a registrar

##### [9.12] SQL do temporal join.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`
- **Recurso ou Mecanismo de Automação:** Script SQL de temporal join `FOR SYSTEM_TIME AS OF t.$rowtime`
- **Evidência Encontrada:** Consulta SQL SELECT transações LEFT JOIN accounts FOR SYSTEM_TIME AS OF versionada e validada.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.13] Estado do statement.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/etapa-9/02_statement_execution.json; scripts/etapa-9/validar_materializacao.py`
- **Recurso ou Mecanismo de Automação:** Execução de statement Flink
- **Evidência Encontrada:** Registro de execução do statement em json.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

##### [9.14] Amostra sanitizada do resultado enriquecido.
- **Status de Conformidade:** `CONFORME` (🟢 CONFORME)
- **Arquivo Responsável:** `evidencias/etapa-9/03_enriched_sample_sanitized.json`
- **Recurso ou Mecanismo de Automação:** Artefato de evidência sanitizado com payload de JOIN
- **Evidência Encontrada:** Arquivo evidencias/etapa-9/03_enriched_sample_sanitized.json com atributos de transação e conta correlacionados.
- **O que está faltando:** Nenhum. Requisito plenamente reproduzível.

---
## 3. LISTAS DE REQUISITOS CONFORMES E NÃO CONFORMES

### C. Lista de Requisitos Conformes (135 itens)
Os 135 itens classificados como `CONFORME` possuem código Terraform declarado, scripts determinísticos de provisionamento/validação, ou evidências técnicas sanitizadas registradas diretamente nas branches auditadas:
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Criar o Environment e o cluster Kafka (o instrutor começa com recursos vazios). (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Conectar ao cluster e conferir que ele está vazio antes da carga. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Criar/selecionar a identidade de serviço de aplicação/CDC e conceder acesso ao cluster. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Gerar API Key/Secret para o cluster Kafka e conceder os ACLs necessários. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Criar/selecionar a identidade do Schema Registry e gerar sua API Key/Secret. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Guardar IDs, endpoints e credenciais em variáveis de ambiente da sessão; não copiar segredos para o código. (Ref: `scripts/export_foundation_env.py; .env.example`)
- [x] **[Etapa 1 | Atividades do instrutor / execução]** Manter o terminal que contém as variáveis aberto durante a execução. (Ref: `README.md; safety.py`)
- [x] **[Etapa 1 | O que precisamos ter para executar]** Acesso administrativo à organização Confluent. (Ref: `infra/terraform/providers.tf`)
- [x] **[Etapa 1 | O que precisamos ter para executar]** Environment ID, Kafka Cluster ID e bootstrap endpoint. (Ref: `infra/terraform/outputs.tf`)
- [x] **[Etapa 1 | O que precisamos ter para executar]** Identidades de serviço e permissões para Kafka/Schema Registry. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | O que precisamos ter para executar]** API Key/Secret de Kafka e API Key/Secret do Schema Registry. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Critério de conclusão (gate)]** Environment e cluster corretos identificados. (Ref: `infra/terraform/foundation.tf`)
- [x] **[Etapa 1 | Critério de conclusão (gate)]** Identidades e ACLs criados/conferidos. (Ref: `infra/terraform/kafka-acls.tf; infra/terraform/cdc-acls.tf`)
- [x] **[Etapa 1 | Critério de conclusão (gate)]** Credenciais testadas sem expor seus valores. (Ref: `scripts/preflight_foundation.py`)
- [x] **[Etapa 1 | Critério de conclusão (gate)]** Sessão de execução pronta para as próximas etapas. (Ref: `scripts/preflight_foundation.py`)
- [x] **[Etapa 1 | Evidências a registrar]** IDs do Environment e cluster (não secretos). (Ref: `evidencias/v2/20261103T193420Z-foundation-ids.txt; infra/terraform/outputs.tf`)
- [x] **[Etapa 1 | Evidências a registrar]** Lista de identidades e ACLs concedidos. (Ref: `infra/terraform/kafka-acls.tf; infra/terraform/cdc-acls.tf`)
- [x] **[Etapa 1 | Evidências a registrar]** Resultado booleano de presença das variáveis/credenciais, nunca os valores. (Ref: `scripts/export_foundation_env.py; .env.example`)
- [x] **[Etapa 2 | Atividades do instrutor / execução]** Criar o projeto/banco de dados (no vídeo, Neon). (Ref: `infra/terraform/aiven-postgres.tf`)
- [x] **[Etapa 2 | Atividades do instrutor / execução]** Copiar a connection string e configurá-la no ambiente de execução. (Ref: `scripts/export_postgres_env.py; infra/terraform/outputs.tf`)
- [x] **[Etapa 2 | Atividades do instrutor / execução]** Executar o SQL de criação das tabelas e carga inicial. (Ref: `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`)
- [x] **[Etapa 2 | Atividades do instrutor / execução]** Conferir que os dados foram carregados no schema payments. (Ref: `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`)
- [x] **[Etapa 2 | O que precisamos ter para executar]** Acesso administrativo ao banco de origem. (Ref: `infra/terraform/outputs.tf; scripts/export_postgres_env.py; scripts/fetch_aiven_ca.py`)
- [x] **[Etapa 2 | O que precisamos ter para executar]** Host, porta, database, usuário e conexão TLS. (Ref: `infra/terraform/outputs.tf; scripts/export_postgres_env.py; scripts/fetch_aiven_ca.py`)
- [x] **[Etapa 2 | O que precisamos ter para executar]** SQL de DDL e seed fornecido/preparado para o desafio. (Ref: `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`)
- [x] **[Etapa 2 | O que precisamos ter para executar]** Confirmação de que o serviço/provedor permite CDC por replicação lógica. (Ref: `infra/terraform/aiven-postgres.tf`)
- [x] **[Etapa 2 | O que precisamos ter para executar]** No nosso caso: acesso ao Aiven e credenciais válidas, sem expô-las. (Ref: `infra/terraform/aiven-postgres.tf`)
- [x] **[Etapa 2 | Critério de conclusão (gate)]** Replicação lógica habilitada e comprovada no provedor. (Ref: `infra/terraform/aiven-postgres.tf`)
- [x] **[Etapa 2 | Critério de conclusão (gate)]** Connection string válida para a sessão de trabalho. (Ref: `scripts/export_postgres_env.py; infra/terraform/outputs.tf`)
- [x] **[Etapa 2 | Critério de conclusão (gate)]** Tabelas do schema esperado criadas e carga inicial concluída. (Ref: `database/migrations/01_schema.sql; database/seeds/02_seed.sql; scripts/database_stage2.py`)
- [x] **[Etapa 2 | Evidências a registrar]** Evidência da configuração de replicação lógica habilitada. (Ref: `infra/terraform/aiven-postgres.tf`)
- [x] **[Etapa 2 | Evidências a registrar]** Saída de validação de conexão sem imprimir connection string. (Ref: `scripts/export_postgres_env.py; infra/terraform/outputs.tf`)
- [x] **[Etapa 2 | Evidências a registrar]** Contagens das tabelas após a carga. (Ref: `scripts/database_stage2.py; evidencias/v2/20261103T215429Z-database-counts.txt`)
- [x] **[Etapa 3 | Atividades do instrutor / execução]** Consultar as contagens das entidades carregadas. (Ref: `scripts/evidence_stage3.py; database/validation/04_verify.sql`)
- [x] **[Etapa 3 | Atividades do instrutor / execução]** O vídeo apresenta como referência: 200 clientes, 240 contas, 320 cartões, 360 estabelecimentos/merchants e 2.000 transações. (Ref: `scripts/evidence_stage3.py; database/validation/04_verify.sql`)
- [x] **[Etapa 3 | Atividades do instrutor / execução]** Executar o SQL de preparação/alteração da senha do usuário CDC. (Ref: `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`)
- [x] **[Etapa 3 | Atividades do instrutor / execução]** Definir uma senha forte para o usuário CDC. (Ref: `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`)
- [x] **[Etapa 3 | Atividades do instrutor / execução]** Criar a identidade/API Key destinada ao Kafka Connect (o instrutor também a chama de CDC Writer). (Ref: `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`)
- [x] **[Etapa 3 | O que precisamos ter para executar]** SQL de conferência das tabelas. (Ref: `database/validation/04_verify.sql`)
- [x] **[Etapa 3 | O que precisamos ter para executar]** Usuário com privilégio administrativo suficiente para preparar o usuário CDC. (Ref: `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`)
- [x] **[Etapa 3 | O que precisamos ter para executar]** Definição dos privilégios que o conector precisa no PostgreSQL. (Ref: `scripts/configure_cdc_user.py`)
- [x] **[Etapa 3 | O que precisamos ter para executar]** Identidade e credencial Kafka Connect no Confluent. (Ref: `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`)
- [x] **[Etapa 3 | O que precisamos ter para executar]** Armazenamento seguro da senha e da API Key/Secret. (Ref: `scripts/export_foundation_env.py; scripts/configure_cdc_user.py`)
- [x] **[Etapa 3 | Critério de conclusão (gate)]** Contagens conferidas ou divergências explicadas. (Ref: `scripts/evidence_stage3.py; database/validation/04_verify.sql`)
- [x] **[Etapa 3 | Critério de conclusão (gate)]** Usuário CDC preparado com os privilégios necessários. (Ref: `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`)
- [x] **[Etapa 3 | Critério de conclusão (gate)]** Credencial Kafka Connect criada e disponível ao Terraform/conector. (Ref: `infra/terraform/foundation.tf; infra/terraform/cdc-acls.tf`)
- [x] **[Etapa 3 | Evidências a registrar]** Contagens por tabela. (Ref: `scripts/evidence_stage3.py; database/validation/04_verify.sql`)
- [x] **[Etapa 3 | Evidências a registrar]** Confirmação de existência/estado do usuário CDC sem exibir senha. (Ref: `scripts/configure_cdc_user.py; database/security/03_cdc_grants.sql`)
- [x] **[Etapa 3 | Evidências a registrar]** Confirmação de presença da credencial do Kafka Connect sem exibir o segredo. (Ref: `scripts/export_foundation_env.py; scripts/configure_cdc_user.py`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** Selecionar as tabelas de origem que serão capturadas (o áudio menciona transactions, accounts e cards; a enumeração está parcialmente redundante na transcrição). (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** Gerar o arquivo/configuração do conector. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** Executar a criação do conector. (Ref: `scripts/apply_cdc_connector.py; scripts/plan_cdc_connector.py`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** O instrutor gera o arquivo para executar e depois o remove do repositório para não acumular artefatos temporários. (Ref: `scripts/teardown_cdc_connector.py; evidencias/v2/stage4-teardown-plan.md`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** Aguardar a propagação/criação dos tópicos (o instrutor comenta que pode levar cerca de dois minutos). (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`)
- [x] **[Etapa 4 | Atividades do instrutor / execução]** Conferir o status RUNNING do conector e a existência dos tópicos. (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`)
- [x] **[Etapa 4 | O que precisamos ter para executar]** Banco preparado e usuário CDC funcional. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | O que precisamos ter para executar]** Host/porta/database/schema e credencial CDC. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | O que precisamos ter para executar]** Kafka Connect API Key/Secret e cluster de destino. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | O que precisamos ter para executar]** Configuração Debezium compatível com o banco e com as tabelas. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | O que precisamos ter para executar]** Terraform e lifecycle scripts já existentes no nosso repositório. (Ref: `infra/terraform/cdc-connector.tf`)
- [x] **[Etapa 4 | Critério de conclusão (gate)]** Conector criado pelo mecanismo Terraform já existente. (Ref: `scripts/apply_cdc_connector.py; scripts/plan_cdc_connector.py`)
- [x] **[Etapa 4 | Critério de conclusão (gate)]** Estado do conector RUNNING. (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`)
- [x] **[Etapa 4 | Critério de conclusão (gate)]** Tópicos CDC esperados criados no Kafka. (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`)
- [x] **[Etapa 4 | Evidências a registrar]** Evidência do Terraform apply bem-sucedido. (Ref: `evidencias/v2/stage4-terraform-apply.txt; evidencias/v2/20261104T010803Z-stage4-terraform-apply.json`)
- [x] **[Etapa 4 | Evidências a registrar]** Status do conector. (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-connector-status.json`)
- [x] **[Etapa 4 | Evidências a registrar]** Lista de tópicos gerados. (Ref: `scripts/verify_and_teardown_cdc.py; evidencias/v2/stage4-cdc-topics.json`)
- [x] **[Etapa 4 | Evidências a registrar]** Evidência de teardown planejado para encerrar o recurso faturável após a janela de teste. (Ref: `scripts/teardown_cdc_connector.py; evidencias/v2/stage4-teardown-plan.md`)
- [x] **[Etapa 5 | Atividades do instrutor / execução]** Executar um consumidor simples para ler os tópicos. (Ref: `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`)
- [x] **[Etapa 5 | Atividades do instrutor / execução]** Confirmar que existem eventos nos tópicos. (Ref: `evidencias/v2/stage5-cdc-consumer.json; src/consumer/audit_cdc.py`)
- [x] **[Etapa 5 | Atividades do instrutor / execução]** Executar uma inserção e uma exclusão na origem. (Ref: `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`)
- [x] **[Etapa 5 | Atividades do instrutor / execução]** Inspecionar os eventos resultantes e os campos before/after quando aplicáveis. (Ref: `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`)
- [x] **[Etapa 5 | Atividades do instrutor / execução]** Confirmar que o evento de exclusão aparece com a semântica esperada. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | O que precisamos ter para executar]** Conector RUNNING. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | O que precisamos ter para executar]** Tópicos CDC criados. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | O que precisamos ter para executar]** Credencial Kafka com permissão de consumo. (Ref: `infra/terraform/consumer-cdc-acl.tf; scripts/plan_stage5_consumer_acl.py`)
- [x] **[Etapa 5 | O que precisamos ter para executar]** Cliente/CLI ou consumidor usado para ler os tópicos. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | O que precisamos ter para executar]** SQL controlado de INSERT e DELETE em registros de teste. (Ref: `scripts/stage5_cdc_scenario.py; src/consumer/verify_cdc_lifecycle.py`)
- [x] **[Etapa 5 | Critério de conclusão (gate)]** Uma alteração feita no PostgreSQL é observada no tópico correspondente. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | Critério de conclusão (gate)]** O evento de INSERT é identificado. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | Critério de conclusão (gate)]** O evento de DELETE é identificado e seu payload é compreendido. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | Critério de conclusão (gate)]** O consumidor consegue ler os eventos sem erro de autenticação/serialização. (Ref: `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`)
- [x] **[Etapa 5 | Evidências a registrar]** Saída sanitizada do consumidor com operação e chave do registro. (Ref: `src/consumer/audit_cdc.py; src/consumer/validate_cdc_avro.py; evidencias/v2/stage5-cdc-consumer.json`)
- [x] **[Etapa 5 | Evidências a registrar]** Evidência do INSERT e do DELETE correlacionados aos testes. (Ref: `scripts/stage5_cdc_scenario.py`)
- [x] **[Etapa 5 | Evidências a registrar]** Sem imprimir credenciais ou dados pessoais desnecessários. (Ref: `scripts/run_stage5_cdc_window.py`)
- [x] **[Etapa 6 | Atividades do instrutor / execução]** Ativar o contrato/schema para o fluxo. (Ref: `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`)
- [x] **[Etapa 6 | Atividades do instrutor / execução]** Adicionar/testar um campo obrigatório sem valor default, conforme a demonstração. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-schema-evolution-diff.json`)
- [x] **[Etapa 6 | Atividades do instrutor / execução]** Executar a validação de compatibilidade. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`)
- [x] **[Etapa 6 | Atividades do instrutor / execução]** Confirmar que a alteração testada não quebra o contrato existente. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`)
- [x] **[Etapa 6 | O que precisamos ter para executar]** Schema Registry acessível. (Ref: `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`)
- [x] **[Etapa 6 | O que precisamos ter para executar]** API Key/Secret do Schema Registry. (Ref: `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`)
- [x] **[Etapa 6 | O que precisamos ter para executar]** Subjects e schemas dos tópicos envolvidos. (Ref: `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`)
- [x] **[Etapa 6 | O que precisamos ter para executar]** Regra de compatibilidade configurada para o subject. (Ref: `infra/terraform/cdc-subject-compatibility.tf; scripts/stage6_apply_subject_policy.py`)
- [x] **[Etapa 6 | O que precisamos ter para executar]** Versão do schema que será validada. (Ref: `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`)
- [x] **[Etapa 6 | Critério de conclusão (gate)]** Schema registrado/validado. (Ref: `infra/terraform/cdc-schemas.tf; schemas/registry/manifest.json`)
- [x] **[Etapa 6 | Critério de conclusão (gate)]** Teste de compatibilidade concluído. (Ref: `infra/terraform/cdc-schemas.tf`)
- [x] **[Etapa 6 | Critério de conclusão (gate)]** Resultado da validação entendido e registrado. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`)
- [x] **[Etapa 6 | Evidências a registrar]** Subject e versão do schema. (Ref: `scripts/stage6_registry_inventory.py; evidencias/v2/stage6-schema-inventory.json`)
- [x] **[Etapa 6 | Evidências a registrar]** Resultado da validação de compatibilidade. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-compatibility.json`)
- [x] **[Etapa 6 | Evidências a registrar]** Diff da evolução de schema, sem credenciais. (Ref: `scripts/stage6_test_compatibility.py; evidencias/v2/stage6-schema-evolution-diff.json`)
- [x] **[Etapa 7 | Atividades do instrutor / execução]** Criar o Compute Pool. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | Atividades do instrutor / execução]** Selecionar o Environment/cluster correspondente. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | Atividades do instrutor / execução]** Abrir o cluster e localizar o Compute Pool criado. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | O que precisamos ter para executar]** Environment e cluster Confluent corretos. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | O que precisamos ter para executar]** Região compatível com os recursos Kafka/Schema Registry. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | O que precisamos ter para executar]** Permissões para criar/usar Flink Compute Pool. (Ref: `infra/terraform/flink-identity.tf`)
- [x] **[Etapa 7 | O que precisamos ter para executar]** Capacidade/custo planejados para a janela de execução. (Ref: `infra/terraform/flink-compute-pool.tf; evidencias/v2/stage7-compute-pool.json`)
- [x] **[Etapa 7 | Critério de conclusão (gate)]** Compute Pool provisionado e selecionável no ambiente. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | Critério de conclusão (gate)]** Workspace Flink acessível. (Ref: `scripts/stage7_verify_compute_pool.py; evidencias/v2/stage7-compute-pool.json`)
- [x] **[Etapa 7 | Evidências a registrar]** ID/nome/região do Compute Pool. (Ref: `infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 7 | Evidências a registrar]** Estado de provisionamento. (Ref: `scripts/stage7_verify_compute_pool.py; evidencias/v2/stage7-compute-pool.json`)
- [x] **[Etapa 7 | Evidências a registrar]** Evidência do custo/capacidade configurada. (Ref: `infra/terraform/flink-compute-pool.tf; evidencias/v2/stage7-compute-pool.json`)
- [x] **[Etapa 8 | Atividades do instrutor / execução]** O instrutor comenta que precisou executar as alterações uma de cada vez. (Ref: `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`)
- [x] **[Etapa 8 | O que precisamos ter para executar]** Compute Pool disponível. (Ref: `scripts/stage8_show_databases.py; infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 8 | O que precisamos ter para executar]** Tabelas Kafka/SQL já reconhecidas pelo Flink. (Ref: `scripts/stage8_show_databases.py; infra/terraform/flink-compute-pool.tf`)
- [x] **[Etapa 8 | O que precisamos ter para executar]** Definição atual da tabela e metadados de chave. (Ref: `sql/stage8_accounts_primary_key.sql`)
- [x] **[Etapa 8 | O que precisamos ter para executar]** SQL DDL correto para o objeto do projeto. (Ref: `sql/stage8_accounts_primary_key.sql`)
- [x] **[Etapa 8 | Critério de conclusão (gate)]** Alteração de tabela aceita pelo Flink. (Ref: `sql/stage8_accounts_primary_key.sql`)
- [x] **[Etapa 8 | Critério de conclusão (gate)]** Chave primária reconhecida no objeto esperado. (Ref: `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`)
- [x] **[Etapa 8 | Critério de conclusão (gate)]** Nenhum statement concorrente conflitante. (Ref: `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`)
- [x] **[Etapa 8 | Evidências a registrar]** Resultado de sucesso. (Ref: `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`)
- [x] **[Etapa 8 | Evidências a registrar]** Definição final da tabela. (Ref: `scripts/stage8_describe_accounts.py; docs/stage8-evidence.md`)
- [x] **[Etapa 9 | Atividades do instrutor / execução]** Criar uma consulta de enriquecimento usando JOIN. (Ref: `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`)
- [x] **[Etapa 9 | Atividades do instrutor / execução]** Utilizar temporal join, conforme explicado pelo instrutor. (Ref: `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`)
- [x] **[Etapa 9 | Atividades do instrutor / execução]** Definir o tempo de referência da consulta com rowtime/tempo do sistema (o áudio transcreve o trecho SQL de forma imprecisa). (Ref: `sql/etapa-9/04_temporal_join.sql`)
- [x] **[Etapa 9 | Atividades do instrutor / execução]** Executar a consulta e confirmar que o enriquecimento é aceito. (Ref: `scripts/etapa-9/validar_materializacao.py; evidencias/etapa-9/02_statement_execution.json`)
- [x] **[Etapa 9 | O que precisamos ter para executar]** Tabelas de transações e contas acessíveis no Flink. (Ref: `sql/etapa-9/02_describe_transactions.sql; sql/etapa-9/03_describe_accounts.sql`)
- [x] **[Etapa 9 | O que precisamos ter para executar]** Chaves de relacionamento identificadas. (Ref: `sql/etapa-9/02_describe_transactions.sql; sql/etapa-9/03_describe_accounts.sql`)
- [x] **[Etapa 9 | O que precisamos ter para executar]** Coluna temporal/rowtime corretamente definida. (Ref: `sql/etapa-9/04_temporal_join.sql`)
- [x] **[Etapa 9 | O que precisamos ter para executar]** DDL e SQL de enriquecimento. (Ref: `evidencias/etapa-9/02_statement_execution.json; scripts/etapa-9/validar_materializacao.py`)
- [x] **[Etapa 9 | Critério de conclusão (gate)]** Temporal join compilado e executado. (Ref: `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`)
- [x] **[Etapa 9 | Critério de conclusão (gate)]** Resultado contém os atributos esperados da transação e da conta. (Ref: `evidencias/etapa-9/03_enriched_sample_sanitized.json`)
- [x] **[Etapa 9 | Critério de conclusão (gate)]** Sem multiplicação indevida de registros ou perda inexplicada. (Ref: `scripts/etapa-9/validar_materializacao.py`)
- [x] **[Etapa 9 | Evidências a registrar]** SQL do temporal join. (Ref: `sql/etapa-9/04_temporal_join.sql; evidencias/etapa-9/01_temporal_join.sql`)
- [x] **[Etapa 9 | Evidências a registrar]** Estado do statement. (Ref: `evidencias/etapa-9/02_statement_execution.json; scripts/etapa-9/validar_materializacao.py`)
- [x] **[Etapa 9 | Evidências a registrar]** Amostra sanitizada do resultado enriquecido. (Ref: `evidencias/etapa-9/03_enriched_sample_sanitized.json`)

### D. Lista de Requisitos Não Conformes / Parcialmente Conformes (6 itens)
Os 6 itens abaixo apresentam lacunas de reprodutibilidade estrita, exigindo os planos de melhoria detalhados a seguir:
- [ ] **[Etapa 1 | O que precisamos ter para executar]** Mecanismo seguro para carregar variáveis no PowerShell. — *Status: `PARCIALMENTE CONFORME`*
- [ ] **[Etapa 2 | Atividades do instrutor / execução]** Habilitar Logical Replication nas configurações do projeto. — *Status: `PARCIALMENTE CONFORME`*
- [ ] **[Etapa 2 | Atividades do instrutor / execução]** Confirmar que o Docker está ativo, conforme a demonstração. — *Status: `PARCIALMENTE CONFORME`*
- [ ] **[Etapa 8 | Atividades do instrutor / execução]** Abrir o SQL Workspace associado ao Compute Pool. — *Status: `PARCIALMENTE CONFORME`*
- [ ] **[Etapa 8 | Atividades do instrutor / execução]** Executar ALTER TABLE para adicionar account_id como chave primária, conforme a demonstração. — *Status: `PARCIALMENTE CONFORME`*
- [ ] **[Etapa 8 | Evidências a registrar]** SQL DDL executado. — *Status: `PARCIALMENTE CONFORME`*

---
## 4. PLANO DE MELHORIA OBRIGATÓRIO (INDIVIDUAL PARA CADA ITEM NÃO CONFORME)

### Plano GAP-01 — [Etapa 1] Mecanismo seguro para carregar variáveis no PowerShell.
- **Seção do Checklist:** `O que precisamos ter para executar`
- **Situação Atual Encontrada:** O repositório possui `scripts/export_foundation_env.py`, que exporta as variáveis mascaradas para arquivo `.env` (dotenv) e formato Bash `export KEY=VAL`. Não há script nativo `.ps1` para PowerShell.
- **Problema Específico:** Usuários operando em ambiente Windows nativo (PowerShell) dependem de conversão manual ou ferramentas de terceiros para carregar as variáveis de ambiente com segurança sem vazar segredos no histórico de comandos.
- **Causa Identificada:** Foco exclusivo no ambiente Linux/Codespaces (.devcontainer) durante a implementação da V2.
- **Arquivos a Modificar:** `scripts/export_foundation_env.py`
- **Arquivos a Criar:** `scripts/export_env.ps1`
- **Recursos Terraform / Automação Necessários:** Script de exportação multi-shell com suporte a `Set-Item -Path env:...` ou geração de script `.ps1` com permissões restritas.
- **Alterações Técnicas Recomendadas:** Aprimorar `export_foundation_env.py` para gerar adicionalmente um arquivo `.env.ps1` com comandos `$env:VAR="valor"`, e fornecer um script wrapper `scripts/export_env.ps1`.
- **Dependências para Implementação:** Nenhuma dependência de nuvem. Opera localmente sobre os outputs do Terraform.
- **Passos para Correção:**
  1. Adicionar rotina de geração de `.env.ps1` em `scripts/export_foundation_env.py`.
  2. Adicionar `.env.ps1` ao `.gitignore` para proteção contra commit acidental.
  3. Criar teste unitário em `tests/test_foundation_export.py` validando a geração do arquivo PowerShell.
- **Critério Objetivo de Aceitação:** A execução de `python scripts/export_foundation_env.py` gera tanto `.env` quanto `.env.ps1`, e a execução de `. ./.env.ps1` no PowerShell carrega todas as variáveis necessárias sem erros e sem imprimir valores.
- **Como Comprovar a Reproduzibilidade:** Executar teste unitário automatizado e validar sintaxe no PowerShell via CI/local.

### Plano GAP-02 — [Etapa 2] Habilitar Logical Replication nas configurações do projeto.
- **Seção do Checklist:** `Atividades do instrutor / execução`
- **Situação Atual Encontrada:** O arquivo `infra/terraform/aiven-postgres.tf` declara o recurso `aiven_pg.payments` apenas com os parâmetros `project`, `service_name` e `plan = "free-1-1gb"`. O script `scripts/database_stage2.py` checa em tempo de execução se `wal_level == logical`, o que passa porque a imagem padrão Aiven PG já vem configurada.
- **Problema Específico:** A configuração de `wal_level = logical` não está declarada explicitamente no Infrastructure as Code (Terraform). Se o plano ou a versão da Aiven alterar o padrão em novas criações, a replicação lógica CDC falhará de forma não determinística.
- **Causa Identificada:** Omissão do bloco de configuração avançada `pg_user_config` no recurso Terraform `aiven_pg`.
- **Arquivos a Modificar:** `infra/terraform/aiven-postgres.tf`
- **Arquivos a Criar:** `Nenhum`
- **Recursos Terraform / Automação Necessários:** Bloco `pg_user_config` dentro do resource `aiven_pg.payments`.
- **Alterações Técnicas Recomendadas:** Adicionar explicitamente em `infra/terraform/aiven-postgres.tf`: `pg_user_config { pg { wal_level = "logical" } }`.
- **Dependências para Implementação:** Provedor Terraform Aiven (`aiven/aiven`).
- **Passos para Correção:**
  1. Atualizar o arquivo `infra/terraform/aiven-postgres.tf` incluindo `pg_user_config` com `wal_level = "logical"`.
  2. Executar `terraform validate` para confirmar compatibilidade do schema do provider Aiven.
  3. Validar se planos gratuitos Aiven aceitam a propriedade via schema provider.
- **Critério Objetivo de Aceitação:** `terraform plan` reflete `wal_level = "logical"` gerenciado via IaC como configuração explícita e obrigatória do banco.
- **Como Comprovar a Reproduzibilidade:** Executar `terraform plan` e conferir a presença explícita de `pg_user_config.pg.wal_level = "logical"` no plano de execução.

### Plano GAP-03 — [Etapa 2] Confirmar que o Docker está ativo, conforme a demonstração.
- **Seção do Checklist:** `Atividades do instrutor / execução`
- **Situação Atual Encontrada:** O ambiente utiliza Dev Containers / Codespaces, onde o Docker é implicitamente o host do contêiner, mas não há script de verificação de sanidade do daemon Docker incluído na esteira de pré-requisitos.
- **Problema Específico:** Caso um executor tente rodar o projeto fora do devcontainer oficial em uma máquina onde o Docker não esteja em execução, não há um pré-voo (preflight) explícito acusando a ausência do Docker.
- **Causa Identificada:** A suposição de que o executor sempre estará dentro do Dev Container oficial.
- **Arquivos a Modificar:** `scripts/preflight_foundation.py`
- **Arquivos a Criar:** `Nenhum`
- **Recursos Terraform / Automação Necessários:** Checagem via `docker info` / `docker --version` em Python subprocess.
- **Alterações Técnicas Recomendadas:** Incluir uma etapa não-bloqueante ou de diagnóstico no preflight checando a disponibilidade do daemon Docker.
- **Dependências para Implementação:** Binário `docker` no PATH.
- **Passos para Correção:**
  1. Adicionar checagem opcional `check_docker_daemon()` em `scripts/preflight_foundation.py`.
  2. Registrar saída booleana `DOCKER_ACTIVE=True/False` sem abortar caso o executor utilize PostgreSQL na nuvem direta (Aiven).
- **Critério Objetivo de Aceitação:** A execução do preflight emite status explícito `DOCKER_AVAILABLE=True`.
- **Como Comprovar a Reproduzibilidade:** Executar `python scripts/preflight_foundation.py` e conferir log de presença do Docker.

### Plano GAP-04 — [Etapa 8] Abrir o SQL Workspace associado ao Compute Pool.
- **Seção do Checklist:** `Atividades do instrutor / execução`
- **Situação Atual Encontrada:** O arquivo `sql/stage8_accounts_primary_key.sql` e a documentação `docs/stage8-evidence.md` descrevem a execução manual no Workspace Flink SQL do Confluent Cloud.
- **Problema Específico:** Exige interação manual na UI web do Confluent Cloud para executar o statement DDL, quebrando o princípio de reproduzibilidade 100% via código/automação.
- **Causa Identificada:** O Confluent Cloud Flink SQL não possuía suporte maduro no provider Terraform Confluent na época da criação, levando ao uso interativo.
- **Arquivos a Modificar:** `scripts/stage8_describe_accounts.py`
- **Arquivos a Criar:** `scripts/stage8_apply_ddl.py`
- **Recursos Terraform / Automação Necessários:** Automação Python utilizando a Flink Statements REST API (`POST /sql/v1/organizations/.../environments/.../statements`).
- **Alterações Técnicas Recomendadas:** Criar o script `scripts/stage8_apply_ddl.py` que lê `sql/stage8_accounts_primary_key.sql`, submete via API REST oficial do Flink na Confluent Cloud e aguarda o statement alcançar o estado `COMPLETED`.
- **Dependências para Implementação:** Compute pool provisionado (Etapa 7) e credenciais Flink.
- **Passos para Correção:**
  1. Criar `scripts/stage8_apply_ddl.py` baseado na estrutura HTTP de `stage8_describe_accounts.py`.
  2. Ler o arquivo `sql/stage8_accounts_primary_key.sql`.
  3. Enviar POST para o endpoint Flink Statement e fazer polling até status COMPLETED.
  4. Integrar o script ao fluxo reproduzível da Etapa 8.
- **Critério Objetivo de Aceitação:** O DDL de chave primária é aplicado de ponta a ponta via comando `python scripts/stage8_apply_ddl.py` sem abrir o navegador.
- **Como Comprovar a Reproduzibilidade:** Executar o script contra o cluster de teste e conferir retorno `STATEMENT_STATUS=COMPLETED`.

### Plano GAP-05 — [Etapa 8] Executar ALTER TABLE para adicionar account_id como chave primária, conforme a demonstração.
- **Seção do Checklist:** `Atividades do instrutor / execução`
- **Situação Atual Encontrada:** O DDL está salvo em arquivo SQL estático `sql/stage8_accounts_primary_key.sql`, mas depende de submissão externa/manual.
- **Problema Específico:** A execução do ALTER TABLE não possui mecanismo idempotente versionado no repositório que impeça erro caso a chave primária já tenha sido adicionada.
- **Causa Identificada:** Dependência de submissão manual do comando SQL.
- **Arquivos a Modificar:** `sql/stage8_accounts_primary_key.sql`
- **Arquivos a Criar:** `scripts/stage8_apply_ddl.py`
- **Recursos Terraform / Automação Necessários:** Mecanismo idempotente de validação prévia de chave primária via API antes de submeter o ALTER TABLE.
- **Alterações Técnicas Recomendadas:** Fazer com que `scripts/stage8_apply_ddl.py` primeiro execute o `DESCRIBE` (já existente em `stage8_describe_accounts.py`). Se `account_id` já for chave primária (`PRI KEY`), o script encerra com sucesso informando que o estado já é o desejado (idempotência). Caso contrário, submete o ALTER TABLE.
- **Dependências para Implementação:** Conexão autenticada à Flink REST API.
- **Passos para Correção:**
  1. Integrar pré-checagem via DESCRIBE no script `scripts/stage8_apply_ddl.py`.
  2. Se não presente, submeter `ALTER TABLE ... ADD CONSTRAINT pk_accounts PRIMARY KEY (account_id) NOT ENFORCED`.
  3. Confirmar que a chave foi adicionada executando novo DESCRIBE pós-aplicação.
- **Critério Objetivo de Aceitação:** A execução do script é totalmente idempotente e garante que `account_id` esteja definido como chave primária sem falhas de duplicação.
- **Como Comprovar a Reproduzibilidade:** Executar o script duas vezes consecutivas e atestar sucesso em ambas.

### Plano GAP-06 — [Etapa 8] SQL DDL executado.
- **Seção do Checklist:** `Evidências a registrar`
- **Situação Atual Encontrada:** A evidência da execução do DDL foi documentada textualmente no Markdown `docs/stage8-evidence.md`, mas sem o artefato bruto JSON de resposta da API do statement (diferente da Etapa 9, que possui `02_statement_execution.json`).
- **Problema Específico:** Falta de artefato de evidência padronizado e auditável em formato JSON na pasta `evidencias/v2/` ou `evidencias/etapa-8/`.
- **Causa Identificada:** A Etapa 8 foi concluída registrando evidências consolidadas no documento markdown, sem salvar o dump JSON do statement.
- **Arquivos a Modificar:** `docs/stage8-evidence.md`
- **Arquivos a Criar:** `evidencias/v2/stage8-statement-execution.json`
- **Recursos Terraform / Automação Necessários:** Gravação automática da resposta JSON sanitizada no script de aplicação.
- **Alterações Técnicas Recomendadas:** Configurar o novo script `scripts/stage8_apply_ddl.py` para salvar o payload de execução retornado pela Confluent REST API em `evidencias/v2/stage8-statement-execution.json` sanitizando credenciais.
- **Dependências para Implementação:** Execução do `scripts/stage8_apply_ddl.py`.
- **Passos para Correção:**
  1. Adicionar rotina de gravação de evidência em `scripts/stage8_apply_ddl.py`.
  2. Versionar o arquivo de saída gerado.
- **Critério Objetivo de Aceitação:** Arquivo `evidencias/v2/stage8-statement-execution.json` presente contendo statement name, status COMPLETED e metadados de execução.
- **Como Comprovar a Reproduzibilidade:** Validar sintaxe JSON e integridade dos campos.

---
## 5. PRIORIZAÇÃO DAS CORREÇÕES TÉCNICAS

As correções foram classificadas rigorosamente de acordo com o impacto na reprodução autônoma do pipeline:

### 🔴 PRIORIDADE CRÍTICA (Impede a reprodução ou compromete recursos dependentes)
- **GAP-04 & GAP-05 (Etapa 8):** Falta de automação unificada para submissão do DDL de Chave Primária no Flink SQL. *Impacto:* Sem a chave primária em `accounts`, a Etapa 9 (Temporal Join) falha categoricamente ou produz resultados inconsistentes, quebrando a cadeia de downstream.

### 🟠 PRIORIDADE ALTA (Requisito obrigatório ausente ou incompleto no IaC)
- **GAP-02 (Etapa 2):** Ausência da declaração explícita de `wal_level = logical` no recurso Terraform `aiven_pg`. *Impacto:* Se o serviço Aiven for recriado em novo projeto ou plano com configurações padrão restritivas, o Debezium CDC não conseguirá criar slots de replicação.

### 🟡 PRIORIDADE MÉDIA (Automação incompleta ou dependência manual)
- **GAP-01 (Etapa 1):** Ausência de exportador seguro nativo para PowerShell (`.ps1`). *Impacto:* Dificulta a reprodução nativa por operadores em ambiente Windows.

### 🟢 PRIORIDADE BAIXA (Documentação, governança e evidências adicionais)
- **GAP-03 (Etapa 2):** Checagem explícita de daemon Docker no preflight de ambiente.
- **GAP-06 (Etapa 8):** Padronização do arquivo de evidência em JSON bruto sanitizado para o statement DDL da Etapa 8.

---
## 6. RELATÓRIO CONSOLIDADO E PLANO DE EXECUÇÃO

### F. Relação Consolidada de Arquivos que Precisam ser Criados ou Modificados

| Ação | Caminho do Arquivo | Finalidade Técnica |
|---|---|---|
| **Modificar** | `infra/terraform/aiven-postgres.tf` | Adicionar bloco `pg_user_config { pg { wal_level = "logical" } }` para garantia estrita de IaC no Aiven PG |
| **Modificar** | `scripts/export_foundation_env.py` | Adicionar suporte à geração de variáveis no padrão PowerShell (`.env.ps1`) |
| **Modificar** | `scripts/preflight_foundation.py` | Incluir verificação de disponibilidade do Docker no diagnóstico de ambiente |
| **Criar** | `scripts/stage8_apply_ddl.py` | Script Python determinístico e idempotente que aplica o DDL Flink via REST API |
| **Criar** | `evidencias/v2/stage8-statement-execution.json` | Registro de evidência padronizado da submissão do DDL de chave primária da Etapa 8 |
| **Modificar** | `.gitignore` | Assegurar que `.env.ps1` e arquivos de sessão temporários sejam ignorados |

### G. Sequência Recomendada de Implementação das Melhorias

1. **Etapa 2 (IaC Hardening):** Atualizar `infra/terraform/aiven-postgres.tf` adicionando `pg_user_config` e executar `terraform validate`.
2. **Etapa 1 (Shell Portability):** Aprimorar `scripts/export_foundation_env.py` para gerar exportação compatível com PowerShell.
3. **Etapa 8 (DDL Automation):** Implementar `scripts/stage8_apply_ddl.py` reutilizando a infraestrutura HTTP já validada em `stage8_describe_accounts.py` e executar a validação de idempotência.
4. **Etapa 8 (Evidence Standardization):** Capturar e versionar o payload sanitizado em `evidencias/v2/stage8-statement-execution.json`.
5. **Validação Geral de Não-Regressão:** Executar a suíte de testes existente (`pytest tests/`) para garantir que nenhuma automação prévia foi impactada.

### H. Critérios de Validação para Comprovar 100% de Conformidade

Para que o projeto alcance **100.0% de conformidade** e seja declarado plenamente aprovado, os seguintes testes objetivos devem ser satisfeitos:
1. `terraform validate` executa sem erros em `infra/terraform/`.
2. `python scripts/export_foundation_env.py` gera `.env` e `.env.ps1` válidos.
3. `python scripts/database_stage2.py check` retorna `WAL_LEVEL_LOGICAL= True` e `COUNT_*` estritamente conferidos.
4. `python scripts/stage8_apply_ddl.py` executa de forma autônoma sem interface gráfica e confirma `PRIMARY_KEY_VALIDATED=True`.
5. `python scripts/etapa-9/validar_materializacao.py` executa o Temporal Join e valida materialização com 0 perdas e 0 multiplicações.
6. A suíte completa `pytest tests/` é executada com 100% de aprovação.