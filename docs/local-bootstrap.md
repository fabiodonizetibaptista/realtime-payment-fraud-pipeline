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
