# Etapa 4 — Escopo de captura CDC

## Objetivo

Conectar o PostgreSQL Aiven ao Kafka Confluent Cloud
utilizando o conector gerenciado PostgresCdcSourceV2.

## Tabelas selecionadas

| Tabela | Finalidade |
|---|---|
| public.transactions | Eventos de pagamentos |
| public.accounts | Enriquecimento com dados das contas |
| public.cards | Identificação dos cartões |
| public.customers | Relacionamento com clientes |
| public.merchants | Dados dos estabelecimentos |
| cdc_internal.heartbeat | Suporte à atividade CDC |

## Configuração

table.include.list=public.customers,public.accounts,public.cards,public.merchants,public.transactions,cdc_internal.heartbeat

publication.name=payments_publication

database.user=cdc_user

snapshot.mode=initial

## Decisões

- Preservar o schema public e o contrato da V1.
- Capturar as cinco tabelas de negócio e o heartbeat.
- Manter 60 merchants conforme decisão da Etapa 3.
- Utilizar cdc_user com privilégios mínimos.
- Utilizar a Service Account CDC existente na V2.
- Não fixar IDs, hosts ou credenciais da V1.
- Gerenciar o conector temporário pelo Terraform.
- Não versionar planos, backups ou credenciais.
- Verificar RUNNING e os tópicos após a criação.
- Garantir destruição controlada do conector após os testes.

## Contrato de nomenclatura

server.name=payments

Tópicos esperados das tabelas de negócio:
payments.public.customers
payments.public.accounts
payments.public.cards
payments.public.merchants
payments.public.transactions

O tópico de heartbeat será identificado dinamicamente,
pois seu nome pode depender do ID do conector.

## Critério de aceitação

O escopo de captura deve ser reproduzido na configuração
Terraform do conector e verificado durante sua execução.
