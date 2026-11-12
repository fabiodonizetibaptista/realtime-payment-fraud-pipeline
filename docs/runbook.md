# Roteiro de execução — do zero ao teardown

Este é o **único** roteiro de comandos do projeto. Ele sobe o pipeline em uma
conta vazia, prova cada camada, derruba tudo e confere que nada restou.
Cada passo traz o critério de **PASS** e o que fazer se falhar.

- Tempo: ~1 h 30 min no total; a parte faturável (conector + Flink) leva ~1 h.
- Custo: coberto pelos créditos de avaliação da Confluent; o Postgres da Aiven
  usa o plano gratuito. Defina um teto antes (recomendado: US$ 5 e 2 h de janela).
- Nenhum comando imprime senhas ou chaves. **Nunca cole o conteúdo do `.env`,
  do State (`*.tfstate`) ou de planos (`*.tfplan`) em issues, chats ou commits.**

## Ambiente — escolha **uma** opção

### Opção A — GitHub Codespaces (recomendada; nada para instalar)

1. No GitHub, abra o repositório e **selecione a branch** no seletor de
   branches (acima da lista de arquivos) → botão **Code** → aba
   **Codespaces** → **Create codespace on &lt;branch&gt;**. Confira que o nome
   do botão mostra a branch certa. Não reaproveite um Codespace antigo
   listado ali: ele pode estar em outra branch ou ter resíduos.
2. Espere a criação terminar: o [`.devcontainer`](../.devcontainer) instala
   sozinho Python 3.12, Terraform 1.16.2, Confluent CLI 4.81 (com checksum) e
   as dependências do `requirements.txt`. **Não crie venv nem rode `pip`.**
3. No terminal do Codespace, confira:

   ```bash
   python --version      # 3.12.x
   terraform version     # 1.16.2 ou maior
   confluent version     # 4.81.0 ou maior
   ```

   Se algum faltar, a instalação automática falhou: rode
   `python .devcontainer/install_tools.py` e confira de novo.
4. Confira a branch e o código: `git branch --show-current` deve mostrar a
   branch escolhida, e não deve existir pasta `.venv`.

O devcontainer também funciona localmente no VS Code com Docker Desktop
(**Dev Containers: Reopen in Container**), com os mesmos passos 2 e 3.

### Opção B — máquina própria (Windows, Linux ou macOS)

Instale Python 3.12+, Terraform 1.16+ e Confluent CLI 4.81+ conforme
[local-bootstrap.md](local-bootstrap.md). Depois, na raiz do repositório:

```bash
python -m venv .venv
. .venv/bin/activate                 # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Shell

Os comandos abaixo valem para bash (Codespaces, Linux, macOS) e PowerShell.
Só quatro coisas mudam:

| Ação | Linux/macOS/Codespaces (bash) | Windows (PowerShell) |
|---|---|---|
| Definir variável de ambiente | `export EVIDENCE_RUN_ID=run-$(date -u +%Y%m%d)` | `$env:EVIDENCE_RUN_ID = "run-" + (Get-Date).ToUniversalTime().ToString("yyyyMMdd")` |
| Capturar output | `ENV_ID=$(terraform -chdir=infra/terraform output -raw environment_id)` | `$ENV_ID = terraform -chdir=infra/terraform output -raw environment_id` |
| Usar variável | `$ENV_ID` | `$ENV_ID` |
| Hora UTC | `date -u +%Y-%m-%dT%H:%M:00Z` | `(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:00Z")` |

## Contas (uma vez)

Contas criadas com login do Google (ou outro SSO) funcionam normalmente.

1. **Aiven:** um projeto existente e um token de API — no console da Aiven,
   **User information → Tokens → Generate token** (`AIVEN_TOKEN`). A Aiven
   não exige login no terminal: o token basta.
2. **Confluent Cloud:** uma **Cloud API key** (não uma chave de cluster) de um
   usuário com permissão de organização — `CONFLUENT_CLOUD_API_KEY` e
   `CONFLUENT_CLOUD_API_SECRET`. O jeito mais seguro é criá-la pela CLI no
   J0.3 (`confluent api-key create --resource cloud`); pelo console é
   **Administration → API keys → Add key → My account → Cloud resource
   management**. O J0.3 confere se ela funciona antes de qualquer criação.

**Por que há duas credenciais da Confluent?** A API key do `.env` é usada pelo
**Terraform** para criar e destruir recursos. A **Confluent CLI** usa a sua
sessão de usuário (`confluent login`, no J0) para consultas e comandos do
Flink — listar ACLs, conectores e statements, rodar SQL e ler o billing.
O login é feito uma vez por Codespace/máquina.
3. Copie `.env.example` para `.env` e preencha **só** estes quatro valores:
   `AIVEN_TOKEN`, `CONFLUENT_CLOUD_API_KEY`, `CONFLUENT_CLOUD_API_SECRET`,
   `TF_VAR_aiven_project`. Todo o resto é gerado pelos scripts.
   **Não preencha senhas do CDC**: `configure_cdc_user.py` cria a sua.

Opcional: cloud/região/nomes da Confluent são variáveis Terraform
(`TF_VAR_confluent_cloud`, `TF_VAR_confluent_region`, padrão `AWS`/`us-east-1`).

---

## J0 — Preparação (sem custo)

> **Como executar os blocos deste roteiro:** cole um bloco por vez e confira o
> PASS antes do próximo. Se um comando falhar, pare ali: os seguintes
> dependem dele. Nada no J0 cria recursos — repetir é seguro.

**J0.1 — Código e `.env` (sem nuvem)**

```bash
python lab.py setup                 # terraform init + validate + checagem de CLIs
python lab.py test                  # testes locais
python -m scripts.check_configuration foundation
```

**PASS:** `BOOTSTRAP_LOCAL_OK`, testes `OK` (mais de 270),
`CONFIG_STATUS=PRESENT_NOT_VERIFIED`.
**Se `MISSING_KEYS=...`:** preencha essas variáveis no `.env` (seção Contas) e
rode só o `check_configuration` de novo.
**Se os testes forem bem menos que 270 ou `scripts.check_configuration` não
existir:** você está numa branch antiga — volte ao passo de Ambiente.

**J0.2 — Login na Confluent CLI**

```bash
confluent login --no-browser
```

Digite o e-mail da conta. Contas Google/SSO **não pedem senha**: a CLI mostra
um link — abra no navegador do seu computador, entre e cole o código exibido.
**PASS:** `Logged in as "..."`.
**Se pedir senha numa conta Google:** o e-mail foi digitado errado (a CLI não
reconheceu a conta). Pressione Enter, confira o e-mail e repita o comando.

**J0.3 — Conta vazia e créditos**

```bash
python scripts/check_cloud_credentials.py   # as chaves do .env funcionam? (só leitura)
confluent environment list          # não pode existir "desafio-final"
confluent billing promo list        # créditos disponíveis
export EVIDENCE_RUN_ID=run-$(date -u +%Y%m%d)   # isola as evidências desta execução
```

**PASS:** `CREDENTIALS_GATE=PASS`; nenhum `desafio-final` na lista; créditos
suficientes para o teto.
**Se `CONFLUENT_CREDENTIALS=FAILED HTTP=401`:** a chave do `.env` não é uma
Cloud API key válida (por exemplo, é chave de cluster ou foi revogada). Crie
uma pela CLI, já logada, e copie os dois valores para o `.env`:

```bash
confluent api-key create --resource cloud --description terraform-desafio
clear    # limpa o segredo da tela depois de copiar
```

Rode `check_cloud_credentials.py` de novo até dar PASS.
**Se `AIVEN_CREDENTIALS=FAILED`:** confira `AIVEN_TOKEN` e o nome técnico do
projeto em `TF_VAR_aiven_project`.
**Se `desafio-final` já existe:** é resíduo de outra execução; derrube-o
(seção [Recuperação](#recuperação)) antes de seguir.
**Armadilha (Windows):** variáveis `PG*` gravadas no perfil do usuário são
herdadas e bloqueiam o J2 (`POSTGRES_ENV_CONFLICT`); remova-as do ambiente.

## J1 — Fundação e recursos permanentes

**J1.1 — Fundação** (environment, cluster Kafka Basic, Schema Registry,
5 identidades e suas chaves: 14 recursos)

```bash
python lab.py plan
python lab.py review-plan                         # PASS: CREATE_COUNT=14, resto 0
python lab.py apply --confirm-foundation          # digite APPLY FOUNDATION
```

**PASS:** `FOUNDATION_APPLY_OK=True`.

**J1.2 — Variáveis geradas**

```bash
python -m scripts.export_foundation_env           # grava as chaves geradas no .env
python -m scripts.check_configuration pipeline    # PASS: CONFIG_STATUS=PRESENT_NOT_VERIFIED
```

**J1.3 — Pipeline** (Postgres Aiven, compute pool Flink, identidades do Flink
e de métricas, role bindings: 16 recursos)

```bash
python lab.py plan-pipeline                       # rode UMA vez
python lab.py review-plan --pipeline              # PASS: CREATE_COUNT=16, resto 0
python lab.py apply-pipeline --confirm-pipeline   # digite APPLY PIPELINE (sem --allow-cdc)
```

**PASS:** `PIPELINE_APPLY_OK=True`.
**Se um apply falhar:** não repita. Confira o que existe com
`terraform -chdir=infra/terraform state list`. Se estiver vazio (por exemplo,
`401` em todos os recursos: credencial inválida), nada foi criado — corrija a
causa e refaça o passo desde o `plan`. Se houver recursos, veja
[Recuperação](#recuperação).
Após este passo, **não rode `plan-pipeline` de novo**: as etapas seguintes têm
scripts próprios que preservam o que já existe.

## J2 — Origem PostgreSQL

O Postgres leva alguns minutos para ficar `RUNNING`; se o primeiro comando
falhar por isso, espere e repita só ele.

```bash
python scripts/export_postgres_env.py
python scripts/fetch_aiven_ca.py
python scripts/bootstrap_postgres.py apply        # schema, publicação e seed
python scripts/configure_cdc_user.py --apply      # cria cdc_user e grava a senha no .env
python -m scripts.check_configuration cdc         # PASS: CDC_PASSWORD_MATCH=True
python scripts/preflight_postgres_cdc.py          # PASS: CDC_PREFLIGHT_GATE= PASS
```

**PASS:** contagens 200/240/320/60/2000, `WAL_LEVEL_LOGICAL`,
`REPLICA_IDENTITY_FULL_OK`, `CDC_BUSINESS_WRITE_DENIED` = `True`.

## J3 — Permissões Kafka (ACLs)

```bash
python scripts/plan_cdc_acls.py                   # PASS: ONLY_EXPECTED_ACL_CREATES=True (11)
python scripts/apply_cdc_acls.py --confirm-acls   # PASS: ACL_APPLY_GATE=PASS
ENV_ID=$(terraform -chdir=infra/terraform output -raw environment_id)
KAFKA_ID=$(terraform -chdir=infra/terraform output -raw kafka_cluster_id)
confluent kafka acl list --environment $ENV_ID --cluster $KAFKA_ID
```

**PASS:** 14 ACLs (11 novas + 3 do Flink); `desafio-consumer` com READ em
`payments.` e no grupo `desafio-`.

---

## J4 — Janela faturável (≤ 2 h a partir daqui)

Anote o início: `WINDOW_START=$(date -u +%Y-%m-%dT%H:%M:00Z)`.

**Condições de parada** — se qualquer uma ocorrer, pule para o J5 (fechamento)
e investigue com tudo desligado: apply do conector falhou; conector fora de
`RUNNING` após 10 min; statement Flink `FAILED`; alerta não observado em 10 min;
janela chegou a 2 h.

### Ingestão (CDC)

```bash
python scripts/plan_cdc_connector.py              # PASS: ONLY_CDC_CONNECTOR_CREATE=True
python scripts/apply_cdc_connector.py             # PASS: CONNECTOR_IN_STATE=True
confluent connect cluster list --environment $ENV_ID --cluster $KAFKA_ID   # repita até RUNNING
confluent kafka topic list --environment $ENV_ID --cluster $KAFKA_ID       # 6 tópicos payments.*
python src/consumer/audit_cdc.py                  # PASS: CONSUMER_GATE= PASS
python scripts/cdc_test_scenario.py --execute     # baseline + INSERT/UPDATE/DELETE + verificação
```

**PASS:** `SCENARIO_GATE=PASS` e `LIFECYCLE_GATE= PASS` com `C`, `U`, `D`, `TOMBSTONE`.
**Se o apply falhar:** rode `python scripts/apply_cdc_connector.py --show-error`
após um novo `plan_cdc_connector.py` (erro mascarado na tela, nada gravado) e
`python scripts/validate_cdc_connector_config.py` (valida campo a campo, sem
criar nada). Confira se ficou conector órfão com `connect cluster list`.

### Contrato (Schema Registry)

```bash
python scripts/plan_schema_compatibility_policy.py    # PASS: POLICY_PLAN_GATE=PASS
python scripts/apply_schema_compatibility_policy.py   # PASS: POLICY_BACKWARD= True
python scripts/verify_schema_compatibility.py         # PASS: COMPATIBILITY_GATE= PASS
python scripts/collect_schema_evidence.py
```

**PASS:** campo opcional com default **aceito**; campo obrigatório sem default
**rejeitado**; nenhuma versão nova registrada.

### Processamento (Flink SQL)

```bash
python lab.py flink-setup                         # PASS: 3 passos MISSING, FLINK_PREFLIGHT=PASSED
python lab.py flink-setup --apply                 # digite APPLY FLINK; PASS: 3 APPLIED
python scripts/validate_temporal_join.py          # PASS: STAGE9_DATA_GATE= PASS
python -m scripts.fraud_stream start --confirm-start
python -m scripts.fraud_stream status             # PASS: STATEMENT_PHASE=RUNNING
python -m scripts.fraud_scenarios execute --confirm-execute   # aguarda o alerta (até 10 min)
python -m scripts.fraud_stream inspect-null       # PASS: ROWS_OBSERVED=0
```

**PASS:** `ALERT_CONFIRMATION=PASS` com `FRAUD_SEQUENCE_MATCHED=True` e
`LEGITIMATE_IN_ANY_MATCH=False`.

### Operação (métricas, inventário)

Espere ~5 min após o último cenário (latência da Metrics API):

```bash
python scripts/collect_metrics_evidence.py --start $WINDOW_START
TODAY=$(python -c "import datetime as d; print(d.datetime.now(d.timezone.utc).date())")
TOMORROW=$(python -c "import datetime as d; print(d.datetime.now(d.timezone.utc).date() + d.timedelta(1))")
python -m scripts.collect_operations_evidence collect --confirm-read \
  --start-date $TODAY --end-date $TOMORROW --environment $ENV_ID --cluster $KAFKA_ID
```

No PowerShell, troque `VAR=$(...)` por `$VAR = (...)` e a quebra `\` por uma linha só.
**PASS:** `METRICS_STATUS=COM_DADOS`, `COLLECTION=PASS`. Se as métricas
vierem vazias, repita em 10 min.

## J5 — Fechamento da janela

```bash
python scripts/teardown_cdc_connector.py --execute   # PASS: TEARDOWN_GATE= PASS
confluent connect cluster list --environment $ENV_ID --cluster $KAFKA_ID   # None found.
```

## J6 — Teardown total

```bash
python lab.py teardown --confirm-destroy   # revise DESTROY_COUNT e FLINK_STATEMENTS_TO_DELETE; digite DESTROY PIPELINE
terraform -chdir=infra/terraform state list      # PASS: vazio
confluent environment list                       # PASS: sem desafio-final
confluent iam service-account list               # PASS: sem desafio-* e payment-fraud-*
```

O teardown apaga primeiro os statements Flink e depois todos os recursos do
State, incluindo a identidade de métricas. No console da Aiven, confirme que o
serviço `payments-postgres` não existe mais. Para deixar o clone pronto para
outra execução do zero:

```bash
rm -rf .local infra/terraform/terraform.tfstate* infra/terraform/.terraform
```

e remova do `.env` tudo exceto as quatro credenciais de conta.

## J7 — Custo (48–72 h depois)

```bash
confluent billing cost list --start-date AAAA-MM-DD --end-date AAAA-MM-DD   # fim exclusivo
```

Enquanto não aparecerem linhas de todos os dias da janela, o custo é parcial.

---

## Recuperação

| Situação | O que fazer |
|---|---|
| Apply falhou | **Não repita.** Planos já submetidos são apagados automaticamente; gere um plano novo pelo mesmo passo e revise. |
| Plano propõe update/destroy inesperado | Não aplique. Confira `terraform -chdir=infra/terraform state list`; o gate bloqueia sozinho. |
| `lab.py teardown` falhou no meio | **Não repita.** `python scripts/reconcile_state.py plan` mostra o que mudou na nuvem; revise e rode `python scripts/reconcile_state.py apply --confirm`; depois um novo `lab.py teardown`. |
| Conector criado fora do State (órfão) | `confluent connect cluster list ...` → `confluent connect cluster delete <id> ...`. |
| Statement Flink `FAILED` | `confluent flink statement describe <nome> --environment $ENV_ID --cloud <cloud> --region <região>` (os do cluster, em minúsculas); o teardown apaga todos. |
| `POSTGRES_ENV_CONFLICT:<VAR>` | Uma variável `PG*` do ambiente difere do `.env`; remova-a do ambiente/perfil. |
| Windows: `confluent` não encontrado após instalar | Feche e reabra o terminal (não redefina o `PATH` inteiro). |

## Limitações conhecidas

- **Lag do consumidor:** a Confluent só oferece `lag summarize` em clusters
  Dedicated; no Basic o lag vem da Metrics API e exige um consumidor que faça
  commit de offsets. O projeto lê os tópicos sem commit (auditoria somente
  leitura), então a série `consumer_lag_offsets` pode vir vazia.
- `confluent kafka cluster list` não informa a data de criação do cluster.
- Scripts em `scripts/` que não aparecem neste roteiro (por exemplo
  `inspect_flink_*`, `verify_flink_compute_pool`, `collect_flink_pool_evidence`,
  `preflight_foundation`) são diagnósticos históricos de etapas anteriores e
  não fazem parte do fluxo.
