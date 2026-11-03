# realtime-payment-fraud-pipeline-v2

Reconstrucao reprodutivel do desafio DIO de pagamentos em tempo real. A V1 e somente referencia historica; a V2 nao importa recursos nem depende dos IDs da V1.

## Ambiente oficial: GitHub Codespaces

O desenvolvimento e a execucao da V2 acontecem no GitHub Codespaces. O notebook local nao precisa instalar Terraform nem Confluent CLI.

O `.devcontainer/devcontainer.json` usa a imagem Python 3.12 e executa `.devcontainer/install_tools.py` na criacao do ambiente. O instalador usa somente a biblioteca padrao do Python para baixar e validar os checksums do [Terraform 1.16.2](https://releases.hashicorp.com/terraform/1.16.2/) e da [Confluent CLI 4.81.0](https://github.com/confluentinc/cli/releases/tag/v4.81.0). Nao ha Dockerfile proprio, Docker-in-Docker, WSL, PowerShell, `curl`, `jq` ou `psql`.

Versoes minimas aceitas pelo projeto:

- Python 3.12+.
- Terraform >= 1.16.0.
- Confluent CLI >= 4.81.0.

O instalador fixa versoes conhecidas para tornar o Codespace reproduzivel; `lab.py setup` aceita versoes superiores e avisa quando forem diferentes.

## Credenciais

O `.env` e opcional. A forma recomendada no Codespaces e cadastrar os segredos em **GitHub > Settings > Codespaces > Codespaces secrets**, concedendo acesso ao repositorio que o usuario criar. Consulte [a documentacao oficial sobre segredos de conta](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces). Os segredos necessários nesta etapa são:

- `CONFLUENT_CLOUD_API_KEY`
- `CONFLUENT_CLOUD_API_SECRET`

Eles devem vir de Codespaces Secrets. `AIVEN_TOKEN` será necessário quando o bloco Aiven for introduzido. As credenciais Kafka e Schema Registry da V2 serão geradas pelo Terraform e exportadas para `.env` pelo script `scripts/export_foundation_env.py`; não reutilize valores da V1.

Se preferir, pode criar `.env` localmente a partir de `.env.example`; ele e ignorado pelo Git. Valores vazios do `.env` sao ignorados. Valores ja existentes no ambiente (incluindo Codespaces Secrets) nunca sao substituidos pelo arquivo. O bootstrap nao exige credenciais reais.

Depois de criar ou alterar um Codespaces secret, pare e reinicie o Codespace para garantir que o valor esteja disponivel no ambiente. Nunca imprima segredos no terminal ou em evidencias.

## Marco 1 — Bootstrap local do Codespace

Na raiz do repositorio:

```text
python lab.py setup
```

O comando confere as versoes, executa `terraform init -lockfile=readonly`, `terraform validate` e verifica os comandos `--help` da Confluent CLI. O backend local e inicializado para permitir State e planos nos marcos seguintes. Nao faz login, nao executa plan/apply e nao consulta nem altera recursos na nuvem.

Testes sem credenciais reais:

```text
python lab.py test
```

Verificacao isolada da CLI:

```text
python lab.py check-cli
```

No Marco 1, antes da declaracao de recursos, `python lab.py teardown` apenas confirmava que nao havia recursos. A partir do Marco 4, o comando bloqueia a operacao enquanto o fluxo remoto de teardown com plano, allow-list separada e verificacao remota nao estiver implementado.

## State e ciclo de vida

O State Terraform sera local no Codespace, no diretorio de trabalho Terraform, e nunca sera enviado ao Git. `.gitignore` exclui `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfvars` e arquivos de plano.

O fluxo esperado de cada janela integrada e `setup -> testes -> teardown` na mesma sessao do Codespace. No Marco 4, o wrapper remoto de apply/teardown ainda nao esta habilitado; nao executar apply antes de sua implementacao e da revisao explicita do plano. O teardown so sera considerado concluido depois de conferir por listagem remota os recursos criados, incluindo statements, conectores e topicos dinamicos de heartbeat.

**Nunca apague o Codespace antes de o teardown ser confirmado por verificacao remota.** Apagar o Codespace antes disso pode eliminar o State local necessario para administrar os recursos ainda existentes.

## Fronteira operacional da V1

Os Marcos 2 (spike Flink) e 3 (destruicao da V1) continuam no notebook, no diretorio original da V1, usando o `scripts/terraform/tf.ps1` existente. Nao copiar o State da V1 para o Codespace nem para backend remoto; nao instalar ferramentas novas no notebook.

Para verificacao remota somente de leitura da V1, usar `tf.ps1 -Action status`. O spike e a destruicao terao branches locais descartaveis na V1. A tag `v1.0` permanece intacta. A destruicao do Marco 3 exigira backup do `terraform.tfstate`, branch descartavel e autorizacao especifica com `-AllowDestroy`.

## Branches por marco

Manter uma branch por marco para que as alteracoes nao se misturem. Cada branch parte da ultima versao aceita; somente depois da validacao do marco o usuario promove suas alteracoes para a branch principal. O usuario cria o repositorio, as branches e faz push; nenhuma automacao deste projeto cria repositorios ou publica codigo.

Nomes sugeridos para as branches V2: `marco-1-codespaces`, `marco-4-foundation`, `marco-5-rebuild`, `marco-6-e2e`, `marco-7-cdc-contracts`, `marco-8-flink-consumer` e `marco-9-delivery`. Os Marcos 2 e 3 sao operacoes no repositorio V1 original, com branches locais separadas `marco-2-flink-spike` e `marco-3-v1-teardown`.

## Contratos de seguranca cobertos por testes

- Redacao do valor exato do segredo, sem filtrar linhas por palavras como `password` ou `secret`.
- Valores vazios do `.env` nao apagam Codespaces Secrets; variaveis existentes nunca sao sobrescritas.
- stderr de processo nativo nao e tratado como falha quando o exit code e zero.
- `try/finally` tenta teardown mesmo quando a execucao falha e preserva a excecao principal.
- Apply exige allow-list; destruicao exige allow-list separada.
- Colecao vazia representa zero recursos.
- Arquivos de evidencia sao UTF-8 sem BOM.
- O codigo operacional nao contem IDs, hosts ou nomes de recursos conhecidos da V1.

As validacoes de ACL heartbeat por prefixo, TransactionalId, `prevent_destroy`, certificado PEM e inicializacao real do conector serao testes estaticos/de integracao adicionados quando os respectivos recursos forem portados. `terraform validate` sozinho nunca sera considerado prova de execucao do conector ou do statement Flink.

## Comandos Confluent previstos

O `setup` testa localmente `--help` para:

- `confluent environment list`
- `confluent kafka cluster list`
- `confluent iam service-account list`
- `confluent kafka acl list` (somente existencia do comando neste marco; flags Cloud verificadas apos login no primeiro marco autenticado)
- `confluent kafka topic list`
- `confluent kafka topic consume`
- `confluent connect cluster list`
- `confluent flink compute-pool list`
- `confluent flink statement list`
- `confluent schema-registry schema compatibility validate`
- `confluent billing cost list`

Nao usar `confluent iam acl list`: o caminho correto para ACLs Kafka no Cloud e `confluent kafka acl list`. A verificacao das flags Cloud `--service-account`, `--cluster` e `--environment` fica para o primeiro marco autenticado.

## Estado do Marco 1

Registro historico do Marco 1: preparacao do Codespace, automacao local e testes. A infraestrutura foi introduzida posteriormente no Marco 4; por isso, as observacoes deste bloco descrevem apenas o estado original do Marco 1.


## Marco 4 — Foundation Confluent

A Foundation declara, sem reutilizar IDs da V1:

- Environment `desafio-final` com Stream Governance Essentials.
- Kafka Basic `desafio-basic` em AWS `us-east-1`, zona unica.
- Identidades `desafio-iac-admin`, `desafio-producer`, `desafio-consumer` e `desafio-schema-registry`.
- API Keys de cluster para o administrador, producer e consumer; API Key do Schema Registry.
- `CloudClusterAdmin` restrito ao CRN do cluster para a identidade técnica de IaC.
- `DeveloperRead` e `DeveloperWrite` restritos aos subjects do Schema Registry.
- ACLs de producer/consumer para o prefixo `desafio-`, inicialmente desabilitadas.

O Kafka Basic não recebe RBAC granular por tópico/grupo; essas permissões são ACLs. O papel `CloudClusterAdmin` é aplicado somente no escopo do cluster para administrar ACLs, sem conceder `EnvironmentAdmin`. No Schema Registry, `DeveloperRead` e `DeveloperWrite` são separados; evitamos `ResourceOwner`, que concederia poderes de gestão de acesso e criação de identidades desnecessários para o contrato de schemas.

### Sequência local

```text
python lab.py setup
python lab.py test
python lab.py plan
```

O primeiro plano deixa `enable_kafka_acls=false`, pois a API Key do `desafio-iac-admin` ainda não foi exportada para o provider. O plano é apenas leitura; não cria recursos. **Não executar apply até revisar o plano, confirmar o custo do cluster e concluir o mecanismo controlado de apply/teardown.**

Depois que a Foundation for aplicada em uma janela autorizada, exporte os outputs sem imprimi-los:

```text
python scripts/export_foundation_env.py
```

O script grava os endpoints e credenciais em `.env` (ignorado pelo Git, modo de arquivo 0600), preserva os valores já existentes e habilita as ACLs para o segundo plano. Os secrets nunca são enviados ao stdout. O provider usa `TF_VAR_foundation_*` para não confundir credenciais V2 com variáveis `KAFKA_API_KEY` antigas da V1.

O State Terraform local contém secrets de API Key. `sensitive=true` oculta valores na CLI, mas não cifra o State. Manter o Codespace e o State protegidos até o teardown confirmado; nunca versionar State ou plan.
