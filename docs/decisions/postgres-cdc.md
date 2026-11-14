# Decisões de arquitetura — Origem PostgreSQL e CDC

## Escopo e volume de dados sintéticos

O cenário utiliza as cinco entidades de negócio abaixo. O volume de `merchants`
foi fixado em 60, em vez dos 360 registros apresentados no exemplo do desafio.
Essa é uma decisão de escopo para os dados sintéticos e **não** uma alteração
do contrato funcional de captura CDC.

| Entidade | Registros na carga sintética |
|---|---:|
| customers | 200 |
| accounts | 240 |
| cards | 320 |
| merchants | 60 |
| transactions | 2000 |

DECISAO_MERCHANTS=60
DIVERGENCIA_MERCHANTS_DOCUMENTADA=True

A decisão é verificada por `scripts/collect_cdc_access_evidence.py`. Alterar a
quantidade de `merchants` exige revisar a carga sintética, seus testes e essa
verificação conjuntamente; não se deve alterar apenas a documentação.

## Identidades e permissões

- A conta PostgreSQL `cdc_user` utiliza `LOGIN`, `REPLICATION` e privilégios
  mínimos de leitura, com acesso controlado ao heartbeat.
- A identidade Kafka Connect é uma **Service Account** gerenciada pelo Terraform.
- Senhas e tokens permanecem fora do Git. Identificadores de recursos são
  resolvidos da infraestrutura implantada, não copiados de um ambiente anterior.

## Configuração da captura

- Conector gerenciado: `PostgresCdcSourceV2` (nome de produto/tipo de conector).
- Banco de origem: PostgreSQL administrado no Aiven.
- Schema transacional: `public`.
- Snapshot inicial: `snapshot.mode=initial`.
- Publicação: `publication.name=payments_publication`.
- Usuário de replicação: `database.user=cdc_user`.

```properties
table.include.list=public.customers,public.accounts,public.cards,public.merchants,public.transactions,cdc_internal.heartbeat
server.name=payments
```

Tópicos esperados para as entidades de negócio:

- `payments.public.customers`
- `payments.public.accounts`
- `payments.public.cards`
- `payments.public.merchants`
- `payments.public.transactions`

O nome do tópico de heartbeat pode depender do conector efetivamente criado;
deve ser descoberto durante a execução.

## Critérios de segurança e aceitação

- O conector deve ser criado e removido pelo procedimento controlado do Terraform.
- Não versionar credenciais, State ou planos do Terraform.
- Verificar estado operacional do conector e chegada de eventos Kafka; a mera
  existência de tópicos não comprova captura CDC funcional.
- Encerrar o conector após os testes para limitar custos recorrentes.

**Limite da evidência:** este documento descreve decisões e o contrato esperado;
não representa, isoladamente, uma nova validação em nuvem.
