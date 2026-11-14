# Evidências — Metadados Flink da tabela de contas

## Ambiente

- Environment: `desafio-final`
- Kafka Cluster: `desafio-basic` (Basic)
- Compute Pool: `payment-fraud-v2` (identificador observado do recurso remoto)
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

O Terraform gerencia a infraestrutura e as permissões. A configuração de
metadados Flink agora possui o procedimento `scripts/flink_setup.py`; a
existência do script não comprova sua execução em uma instalação limpa.

## Registro de validação no SQL Workspace

### Evidencias do SQL Workspace

- Environment: `desafio-final`
- Database: `desafio-basic`
- Tabela: `payments.public.accounts`
- Coluna: `account_id`
- Tipo: `BIGINT NOT NULL`
- Definicao final: `PRIMARY KEY, BUCKET KEY`

O usuario informou que a primeira execucao do ALTER TABLE
foi bem-sucedida. O registro historico dessa execucao
nao foi recuperado no registro historico.

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

O modulo `scripts/flink_setup.py` implementa preflight e aplicacao controlada.
Esta observacao historica nao comprova uma nova execucao do modulo.
O SQL nao deve ser repetido caso a chave primaria ja exista.

### Resultado

Os metadados foram observados no SQL Workspace na execucao registrada.
A aplicacao em ambiente novo depende da verificacao operacional por
`scripts/flink_setup.py`, sem presumir que houve nova execucao.
