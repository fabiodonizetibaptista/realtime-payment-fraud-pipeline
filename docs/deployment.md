# Implantação e portabilidade

## Ambientes suportados como objetivo de projeto

O executor pode ser um terminal Linux, macOS, Windows ou ambiente remoto que disponha das ferramentas exigidas. **Codespaces é opcional**, não é parte da arquitetura. O repositório contém um `.devcontainer/` como conveniência; testes locais em um sistema operacional não provam compatibilidade universal.

O processamento real depende de serviços externos da **Aiven** e da **Confluent Cloud**, além de permissões e orçamento. Uma implantação integral sem serviços externos não está implementada neste repositório.

## Ferramentas e preparação

- Git; Python **3.12+**; Terraform **1.16+**; Confluent CLI **4.81+**, conforme verificações de `lab.py`.
- Instalar dependências Python a partir de `requirements.txt`, preferencialmente em ambiente virtual. No Windows usar o Python do `.venv\Scripts\python.exe`; em Linux/macOS usar o Python do ambiente virtual ativado.
- Validar versões e sintaxe: `python lab.py setup` e `python lab.py check-cli`. `setup` executa `terraform init`, `terraform validate` e checagens de CLI, mas não provisiona recursos.
- Executar `python lab.py test` antes de qualquer operação com nuvem.

## Configurações essenciais

Não versionar `.env`. Usar variáveis de ambiente e/ou `.env` local não publicado. `AIVEN_TOKEN`, `CONFLUENT_CLOUD_API_KEY`, `CONFLUENT_CLOUD_API_SECRET` são credenciais de provedores. O Terraform exige `TF_VAR_aiven_project`, que identifica o **nome técnico de um projeto Aiven pré-existente** (não o ID da organização). `TF_VAR_aiven_pg_service_name` é opcional: por padrão o serviço PostgreSQL recebe o nome `payments-postgres`, desde que esteja disponível no projeto. O recurso `aiven_pg.payments` cria o serviço, **não cria a conta nem o projeto Aiven**.

Os acessos de Kafka/Schema Registry e as variáveis `TF_VAR_foundation_*` podem ser disponibilizados após o primeiro provisionamento via `scripts/export_foundation_env.py`. Não imprimir segredos ou conteúdo bruto de State e planos.

## Preparacao segura do PostgreSQL e preflight CDC (L12 / bloco 3.3)

1. Criar e autorizar suas contas Aiven/Confluent, configurar variaveis do Terraform, revisar o plano e aplicar a Foundation e o provisionamento do PostgreSQL conforme os gates do projeto. **Nao** executar o preflight CDC antes de o servico existir.
2. Obter do painel da Aiven, para o servico criado, os dados de conexao administrativos e o **certificado CA oficial**. Preencher localmente `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` e `PG_CA` (caminho local para o PEM, por exemplo `.local/aiven-ca.pem`); o arquivo PEM e o `.env` nao devem ser versionados. Nao copiar segredos para terminais compartilhados ou logs.
3. Executar `python scripts/bootstrap_postgres.py check` para diagnostico **somente leitura**. Depois de confirmar infraestrutura e custos, executar `python scripts/bootstrap_postgres.py apply` **somente com autorizacao**, pois modifica schema e seed.
4. Criar/verificar o usuario CDC dedicado conforme os scripts SQL versionados, com permissao de replicacao e os privilegios minimos. Configurar `CDC_PGUSER=cdc_user` e `CDC_PGPASSWORD` de forma privada. A senha do conector (`TF_VAR_cdc_connector_password`) deve corresponder a senha configurada para a identidade que o conector utiliza; consultar a definicao Terraform antes de ativar.
5. Executar `python scripts/preflight_postgres_cdc.py`: ele bloqueia localmente e lista **somente nomes** das configuracoes ausentes ou CA inexistente, antes de se conectar. Com acesso disponivel verifica `wal_level`, `max_replication_slots`, `max_wal_senders`, publication, contagens, replica identity, privilegios e login CDC. A existencia do slot de replicacao e apenas informativa; sua criacao e gerenciada no ciclo do conector.
6. `python database/validation/09_cdc_preflight.py show` utiliza variaveis de ambiente de processo (`PGHOST` etc. e `PG_CA`) e **nao** importa automaticamente `.env`. Seu subcomando `drop-slot` **modifica o banco** e nao deve ser utilizado como preflight.

**Limite de evidencia:** sem PostgreSQL provisionado e credenciais proprias nao e possivel confirmar configuracoes remotas. Falha de configuracao local nao equivale a falha de WAL/publication/replicacao. A verificacao TLS exige CA confiavel e hostname correspondente, sem `ssl_context=True` permissivo.

## Sequência lógica e pontos de controle

| Fase | Ação verificada no código | Controle |
|---|---|---|
| Preparação | `python lab.py setup`; `python lab.py test` | Sem provisionamento remoto |
| Plano inicial | `python lab.py plan` | Salva `foundation.tfplan`; revisar antes de aplicar |
| Foundation | `python lab.py apply --confirm-foundation` | Requer revisão/aceite interativo e allowlist de recursos |
| Infraestrutura completa | `python lab.py plan-pipeline`; `python lab.py review-plan --pipeline` | Plano salvo com mudanças permitidas; revisar custos |
| Aplicação completa | `python lab.py apply-pipeline --confirm-pipeline` | Operação remota sujeita a confirmação; se incluir CDC requer também `--allow-cdc` |
| Origem | `python scripts/bootstrap_postgres.py check` | Somente verificação; `apply` modifica DDL/seeds |
| Flink | `python lab.py flink-setup` | Preflight; `--apply` executa DDLs mediante confirmação |
| Regra contínua | `python -m scripts.fraud_stream plan` | Antes de `start --confirm-start` |
| Cenários | `python -m scripts.fraud_scenarios plan` | Antes de `execute --confirm-execute` |

**Atenção:** essa tabela mapeia interfaces verificadas no código, **não é promessa de execução automatizada integral em um único comando**. Dependências entre fases, identidade ativa no CLI, permissões, replicação lógica, origem Kafka e orçamento devem ser conferidos em cada gate. `plan-pipeline` e `apply-pipeline` foram desenhados para bloquear operações inseguras; jamais burlar essas proteções para concluir a demonstração.

## Verificação e encerramento

Depois da implantação, comprovar a existência de recursos na conta correta, os cinco tópicos de tabelas e os eventos CDC. Para o Flink, registrar statements, estados e correspondências produzidas. Ao encerrar, consultar [operação e teardown](operations.md); não excluir o State local antes de verificar a destruição remota.

## Limitantes de portabilidade conhecidos

Referências a Codespaces descrevem apenas a conveniência de execução remota; não configuram dependência nem requisito de sistema operacional. Evite copiar identificadores, State ou credenciais de uma execução anterior. A compatibilidade operacional completa em Windows, Linux e macOS exige execução dos respectivos procedimentos de bootstrap/CLI em cada plataforma; não está comprovada apenas pelos testes unitários.
