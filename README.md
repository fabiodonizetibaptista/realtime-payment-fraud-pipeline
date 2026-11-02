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

O `.env` e opcional. A forma recomendada no Codespaces e cadastrar os segredos em **GitHub > Settings > Codespaces > Codespaces secrets**, concedendo acesso ao repositorio que o usuario criar. Consulte [a documentacao oficial sobre segredos de conta](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces). Os nomes devem corresponder exatamente aos campos de `.env.example`:

- `AIVEN_TOKEN`
- `CONFLUENT_CLOUD_API_KEY`
- `CONFLUENT_CLOUD_API_SECRET`
- `KAFKA_API_KEY`
- `KAFKA_API_SECRET`
- `SCHEMA_REGISTRY_API_KEY`
- `SCHEMA_REGISTRY_API_SECRET`

Se preferir, pode criar `.env` localmente a partir de `.env.example`; ele e ignorado pelo Git. Valores vazios do `.env` sao ignorados. Valores ja existentes no ambiente (incluindo Codespaces Secrets) nunca sao substituidos pelo arquivo. O bootstrap nao exige credenciais reais.

Depois de criar ou alterar um Codespaces secret, pare e reinicie o Codespace para garantir que o valor esteja disponivel no ambiente. Nunca imprima segredos no terminal ou em evidencias.

## Marco 1 — Bootstrap local do Codespace

Na raiz do repositorio:

```text
python lab.py setup
```

O comando confere as versoes, executa `terraform init -backend=false -lockfile=readonly`, `terraform validate` e verifica os comandos `--help` da Confluent CLI. Nao faz login, nao executa plan/apply e nao consulta nem altera recursos na nuvem.

Testes sem credenciais reais:

```text
python lab.py test
```

Verificacao isolada da CLI:

```text
python lab.py check-cli
```

No Marco 1, `python lab.py teardown` apenas confirma que ainda nao ha recursos declarados para destruir. O teardown remoto sera implementado junto com os recursos, usando `try/finally`, plano/allow-list e verificacao por listagem remota.

## State e ciclo de vida

O State Terraform sera local no Codespace, no diretorio de trabalho Terraform, e nunca sera enviado ao Git. `.gitignore` exclui `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfvars` e arquivos de plano.

O fluxo de cada janela integrada sera `setup -> testes -> teardown` na mesma sessao do Codespace. O teardown sera garantido por `try/finally` e so sera considerado concluido depois de conferir por listagem remota os recursos criados, incluindo statements, conectores e topicos dinamicos de heartbeat.

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

Este marco prepara o Codespace, a automacao local e os testes. A infraestrutura ainda nao foi portada; por isso `setup` nao provisiona recursos e `teardown` nao destroi recursos. O State local e o ciclo completo de teardown remoto serao exercitados nos marcos de provisionamento, sempre na mesma sessao do Codespace.
