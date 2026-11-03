# Etapa 3 — Volume de dados e autenticação CDC

## Decisão sobre o volume de merchants

O vídeo de referência do desafio apresenta 360 merchants.

A implementação original da V1 utiliza um seed sintético
determinístico com 60 merchants. Essa implementação foi
reaproveitada na V2, preservando o contrato de dados
já desenvolvido e validado.

Volumes adotados na V2:

| Entidade | Referência do vídeo | V2 |
|---|---:|---:|
| customers | 200 | 200 |
| accounts | 240 | 240 |
| cards | 320 | 320 |
| merchants | 360 | 60 |
| transactions | 2000 | 2000 |

DECISAO_MERCHANTS=60
DIVERGENCIA_MERCHANTS_DOCUMENTADA=True

A diferença é intencional. Não modifica o funcionamento
esperado do pipeline CDC, porque o requisito funcional
consiste em capturar alterações das entidades e processar
transações, não em exigir exatamente 360 estabelecimentos.

O contrato CDC permanece baseado no schema public.
Não é necessário recriar as tabelas ou executar o seed.

## Identidade PostgreSQL

O usuário cdc_user foi criado na V2 com LOGIN,
REPLICATION e privilégios mínimos de leitura,
além da atualização controlada do heartbeat.

A senha é mantida fora do Git, na configuração
local do ambiente de execução.

## Identidade Kafka Connect

A identidade CDC é gerenciada pelo Terraform
da Foundation Confluent Cloud.

Modalidade escolhida: SERVICE_ACCOUNT.

O futuro conector deverá utilizar a referência
dinâmica ao ID da Service Account CDC, sem fixar
IDs herdados da V1.

A autenticação efetiva será validada quando o
conector for criado e executado.
