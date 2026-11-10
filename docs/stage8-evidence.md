# Etapa 8 — Evidências e critérios de conclusão

## Ambiente

- Environment: `desafio-final`
- Kafka Cluster: `desafio-basic` (Basic)
- Compute Pool: `payment-fraud-v2`
- Tabela: `payments.public.accounts`

## Evidências funcionais

- SQL Workspace acessado com sucesso.
- `SHOW DATABASES`: cluster esperado visível.
- `DESCRIBE`: execução concluída.
- `account_id`: `BIGINT NOT NULL`.
- Metadados finais: `PRIMARY KEY, BUCKET KEY`.
- A execução bem-sucedida específica do ALTER TABLE não foi registrada nos logs desta sessão; o estado final foi confirmado no Workspace.
- Statements listados pela API: 6.
- Statements COMPLETED: 5.
- Statements FAILED: 1.
- Statements não terminais: 0.
- Nenhum statement concorrente identificado entre os retornados pela API à identidade consultada.

## Limpeza

- Permissões de leitura e descoberta preservadas.
- Permissões experimentais de alteração: remoção remota ainda pendente de aplicação.
- Conector CDC permaneceu desativado.
- SQL DDL registrado em `sql/enrichment/accounts_primary_key.sql`.

## Reprodutibilidade

A definição SQL está registrada, mas sua aplicação automática em uma recriação limpa ainda não foi implementada nem validada. O Terraform gerencia a infraestrutura e as permissões; o DDL requer uma etapa operacional própria.

## Fechamento formal da Etapa 8

### Evidencias do SQL Workspace

- Environment: `desafio-final`
- Database: `desafio-basic`
- Tabela: `payments.public.accounts`
- Coluna: `account_id`
- Tipo: `BIGINT NOT NULL`
- Definicao final: `PRIMARY KEY, BUCKET KEY`

O usuario informou que a primeira execucao do ALTER TABLE
foi bem-sucedida. O registro historico dessa execucao
nao foi recuperado nesta etapa.

Uma tentativa posterior de executar novamente o mesmo DDL
foi rejeitada porque a tabela ja possuia a chave primaria
`account_id`. Essa rejeicao nao representa uma nova
alteracao bem-sucedida.

O DESCRIBE realizado no SQL Workspace confirmou o estado
final desejado. A captura de tela foi fornecida na
conversa de validacao, mas nao foi incorporada como
arquivo ao repositorio.

### Gate de conclusao

- Definicao final da tabela: validada
- Chave primaria reconhecida: validada
- Statements consultados: 6
- Statements COMPLETED: 5
- Statements FAILED: 1
- Statements nao terminais: 0
- Limpeza das permissoes experimentais: concluida
- FlinkDeveloper, Operator e permissoes de leitura: preservados
- Conector CDC: mantido desativado

### Reprodutibilidade

O SQL DDL esta registrado em
`sql/enrichment/accounts_primary_key.sql`.

A aplicacao automatica desse DDL em uma recriacao limpa
ainda nao foi implementada nem validada. O script SQL
nao deve ser repetido caso a chave primaria ja exista.

### Resultado

Etapa 8 concluida funcionalmente, com ressalva
documental sobre o historico da primeira execucao
e pendencia explicita de automacao do DDL.
