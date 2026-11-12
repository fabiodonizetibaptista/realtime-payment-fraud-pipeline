# Implantação e portabilidade

Os comandos de implantação estão **somente** em [runbook.md](runbook.md). Este
documento explica o que o roteiro pressupõe e o que muda entre ambientes.

## Ambientes

- **Codespaces é opcional.** O [`.devcontainer/`](../.devcontainer) instala
  Python 3.12, Terraform 1.16.2, Confluent CLI 4.81 (com checksum) e o
  `requirements.txt`; é o caminho com menos variáveis.
- **Máquina própria:** Linux/macOS (shell) ou Windows (PowerShell) com Python
  3.12+, Terraform 1.16+ e Confluent CLI 4.81+ — instalação em
  [local-bootstrap.md](local-bootstrap.md). `python lab.py setup` confere as
  versões, roda `terraform init` e `validate` e não cria nada na nuvem.

O processamento depende de serviços externos: **Aiven** (projeto existente;
o Terraform cria só o serviço PostgreSQL) e **Confluent Cloud** (Cloud API key
com permissão de organização). Não há modo local equivalente.

## Configuração

- O `.env` (fora do Git) começa com quatro valores do operador: `AIVEN_TOKEN`,
  `CONFLUENT_CLOUD_API_KEY`, `CONFLUENT_CLOUD_API_SECRET` e
  `TF_VAR_aiven_project` (nome técnico do projeto Aiven, não o ID da
  organização). Variáveis definidas no ambiente têm precedência sobre o `.env`.
- Todo o resto é **gerado** durante a execução: `export_foundation_env.py`
  (chaves Kafka/Schema Registry), `export_postgres_env.py` e
  `fetch_aiven_ca.py` (conexão e CA do Postgres), `configure_cdc_user.py`
  (cria o `cdc_user` com senha nova e grava `CDC_PGPASSWORD` e
  `TF_VAR_cdc_connector_password` com o mesmo valor). Não preencha esses
  valores à mão nem copie de outra execução.
- Opcionais: `TF_VAR_aiven_pg_service_name` (padrão `payments-postgres`),
  `TF_VAR_confluent_cloud` / `TF_VAR_confluent_region` (padrão `AWS` /
  `us-east-1`), `TF_VAR_confluent_environment_name` /
  `TF_VAR_kafka_cluster_name` (padrão `desafio-final` / `desafio-basic`, que
  também são o catálogo e o database do Flink). Os scripts leem esses valores
  do State, sem nada fixo.

## Diferenças conhecidas entre ambientes

| Situação | Efeito | Como evitar |
|---|---|---|
| Variáveis `PG*` gravadas no perfil do usuário (Windows) | `POSTGRES_ENV_CONFLICT:<VAR>` no J2 | Remover do perfil; o `.env` é a fonte |
| Confluent CLI instalada com o terminal aberto (Windows) | `confluent` não encontrado | Fechar e reabrir o terminal |
| Login em Codespaces/SSO | Navegador indisponível | `confluent login --no-browser` |
| `date -d` (GNU) | Não existe no macOS | O roteiro usa Python para datas relativas |

A compatibilidade foi exercitada em Windows (PowerShell) na run-20261111; a
execução guiada só pela documentação em Codespaces é o próximo gate
(ver [README](../README.md#estado-da-reprodutibilidade)).
