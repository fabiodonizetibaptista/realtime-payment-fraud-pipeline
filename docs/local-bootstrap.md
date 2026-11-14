# Bootstrap local multiplataforma

**Objetivo:** preparar qualquer maquina compativel com Windows, macOS ou Linux sem exigir GitHub Codespaces. O repositório não contém credenciais e não pode provisionar contas externas automaticamente.

## 1. Python e Git

Instale Git e Python >= 3.12 a partir dos canais oficiais do seu sistema. Abra um terminal na raiz do clone e use o interpretador instalado (Windows: `py -3.12` se disponível; Linux/macOS: `python3`). Depois, crie um virtualenv e instale `requirements.txt` usando o Python desse ambiente. Isso deve acontecer antes de `lab.py setup`.

## 2. Terraform >= 1.16 e Confluent CLI >= 4.81

Execute `python -m scripts.bootstrap_local instructions` para orientacoes específicas do seu sistema. Fontes oficiais:

- [Terraform — instalação da HashiCorp](https://developer.hashicorp.com/terraform/install)
- [Confluent CLI — instalação oficial](https://docs.confluent.io/confluent-cli/current/install.html)
- [Confluent CLI — versões para Windows e outras plataformas](https://github.com/confluentinc/cli/releases)

No **Windows**, faça download das versões correspondentes à arquitetura, verifique a integridade com checksums publicados pelo fornecedor, extraia os executáveis para diretórios persistentes e acrescente os diretórios ao `PATH` do usuário. Reabra o PowerShell. A Confluent CLI costuma vir como `confluent.exe` em ZIP.

No **macOS**, uma opção com Homebrew é:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
brew install confluentinc/tap/cli
```

No **Linux**, siga o procedimento da sua distribuição na documentação oficial (repositorios HashiCorp/Confluent para APT ou YUM/DNF, ou binários verificados). Não execute scripts remotos diretamente em shells sem auditar a origem.

Verifique a disponibilidade de `terraform version` e `confluent version`, sem realizar login. Confirme o caminho de execução com `Get-Command confluent` no PowerShell ou `command -v confluent` em shells POSIX. Se faltarem ferramentas no `PATH`, revise a instalação e abra um novo terminal.

### Recuperação guiada quando uma CLI está ausente ou abaixo do mínimo

Depois de instalar Python 3.12+ e criar o `.venv`, execute **com o Python desse ambiente**:

```powershell
# Windows
.\.venv\Scripts\python.exe -m scripts.bootstrap_local repair-tools
```

```bash
# Linux e macOS
.venv/bin/python -m scripts.bootstrap_local repair-tools
```

O comando consulta somente as versões locais, indica se Terraform >= 1.16 e Confluent CLI >= 4.81 estão disponíveis e imprime as ações de recuperação apropriadas ao sistema. **Não instala nada, não baixa artefatos e não faz login.** Um código de saída `1` significa dependência pendente, não falha do pipeline.

**Windows:** para Confluent CLI, baixe o ZIP Windows AMD64 no [repositório oficial](https://github.com/confluentinc/cli/releases/latest), confirme arquitetura e integridade, extraia `confluent.exe` para um diretório persistente (exemplo: `C:\Tools\Confluent\`) e acrescente **o diretório**, não o arquivo, ao `PATH` do usuário pelas configurações de Variáveis de Ambiente. Use a mesma abordagem com o executável do Terraform baixado do [site oficial](https://developer.hashicorp.com/terraform/install), se necessário. Abra outro PowerShell, use `Get-Command confluent` e `Get-Command terraform` e execute novamente o diagnóstico. Não copie binários para dentro do `.venv`.

**macOS:** use os comandos Homebrew documentados acima, ou baixe os binários oficiais para a arquitetura correspondente (Apple Silicon ou Intel). Confirme com `command -v terraform` e `command -v confluent` e com os respectivos comandos de versão.

**Linux:** para Debian/Ubuntu, a Confluent disponibiliza um [repositório APT oficial](https://docs.confluent.io/confluent-cli/current/install.html); outras distribuições podem seguir o método YUM/DNF ou binários oficiais. A instalação do Terraform depende da distribuição: consulte o repositório oficial HashiCorp. Confira arquiteturas, versões e `PATH` com `command -v`.

Se o diagnóstico detectar uma versão inferior ao mínimo, atualize pelo fornecedor; **não altere os requisitos de versão para contornar a falha**. Execute `python -m scripts.check_environment` depois da recuperação. Estas instruções não substituem a configuração de contas e credenciais externas.

## 3. Configuração local, sem publicar segredos

Na raiz do projeto:

```text
python -m scripts.bootstrap_local init-env
python -m scripts.check_environment
```

`init-env` cria `.env` copiando `.env.example`, somente quando ainda não existe. Nunca substitui um `.env` anterior e não exibe os valores. Em Linux/macOS, cria o arquivo com permissão `0600` quando suportada; no Windows, valem as permissões herdadas do diretório. Garanta que a pasta não seja compartilhada inadvertidamente.

Preencha os parâmetros e segredos **por conta própria** conforme o guia de implantação. As credenciais não são exportadas pelo bootstrap, e a ausência de `.env` em um clone limpo é normal. Nunca versionar `.env`, State, planos Terraform ou tokens.

## 4. Verificações e limites

Use o Python do seu venv para `python -m scripts.check_environment` e `python lab.py test`. O verificador é somente leitura: não consulta nuvem, não valida permissões dos provedores e não confirma CDC/Flink. Um `READY=False` indica dependências locais ausentes; use as orientações do bootstrap. Depois, `python lab.py setup` executa `terraform init` e `terraform validate`, podendo baixar providers, mas não cria recursos em nuvem.

**Não execute `plan`, `apply`, conectores ou `start` até configurar contas Aiven e Confluent Cloud, validar custos e compreender as confirmações de cada fase.** Consulte [Implantação](deployment.md) para o fluxo Foundation -> configuração -> pipeline.

## 5. Diagnostico local por fase (sem acesso a nuvem)

Depois de criar o `.env`, execute **somente a fase correspondente**:

```text
python -m scripts.check_configuration foundation
python -m scripts.check_configuration pipeline
python -m scripts.check_configuration postgres
python -m scripts.check_configuration cdc
```

- `foundation`: requer credenciais administrativas Aiven/Confluent e projeto Aiven, **nao** requer outputs da Foundation ainda nao criada.
- `pipeline`: requer os outputs `TF_VAR_foundation_*`, gerados apos o `apply` da Foundation por `python -m scripts.export_foundation_env`.
- `postgres`: requer credenciais de conexao e caminho `PG_CA` do PostgreSQL provisionado.
- `cdc`: requer adicionalmente `CDC_PGUSER`, `CDC_PGPASSWORD` e senha do conector, todos gravados por `python scripts/configure_cdc_user.py --apply` (nao preencha a mao); o diagnostico imprime `CDC_PASSWORD_MATCH=True/False` sem mostrar valores.

O diagnostico mostra apenas **nomes** das chaves ausentes, nunca os valores.
`CONFIG_STATUS=PRESENT_NOT_VERIFIED` significa unicamente presenca local,
**nao** autenticacao, autorizacao, conectividade nem funcionamento dos servicos.
O verificador nao testa a existencia do arquivo CA ou permissões remotas;
use o preflight PostgreSQL especifico depois de provisionar o banco.
No Windows e em outros ambientes, cada clone deve ter seu proprio `.env` local
(ou segredos de ambiente), sem copiar o arquivo ao Git.

### Conflito de variaveis de ambiente PostgreSQL (Windows e outros sistemas)

O `scripts/export_postgres_env.py` registra no `.env` os parametros do PostgreSQL
provisionado pelo Terraform State deste clone. Se uma variavel de processo
(`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` ou `PG_CA`) tiver
valor diferente daquele presente no `.env`, o `bootstrap_postgres.py` bloqueia
a conexao com `POSTGRES_ENV_CONFLICT:<NOME_DA_CHAVE>` sem exibir valores.
Isso impede conexao silenciosa a um servico de execucoes anteriores.

No PowerShell, inspecione apenas a presenca das variaveis com
`Get-ChildItem Env:PG* | Select-Object -ExpandProperty Name`, sem imprimir valores.
Para remover somente uma variavel herdada da sessao atual, use
`Remove-Item Env:PGHOST -ErrorAction SilentlyContinue`. Se a variavel voltar em
todo terminal novo, ela esta gravada no perfil do usuario; remova com
`[Environment]::SetEnvironmentVariable("PGHOST", $null, "User")` (caso real da
run-20261111). Em seguida, execute
`python scripts/bootstrap_postgres.py check`. Nao altere a configuracao TLS
para contornar erros.
