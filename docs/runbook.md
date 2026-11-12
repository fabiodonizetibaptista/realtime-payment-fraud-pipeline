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

### Shell e como ler os resultados

Os comandos valem para bash (Codespaces, Linux, macOS). No Windows, use
**PowerShell 7** (`pwsh`), que aceita o mesmo encadeamento; no Windows
PowerShell 5.1, rode os comandos de cada bloco um por vez.

**Cada bloco é encadeado com `&&` e termina com uma linha explícita:**

- `>>> J1.1 OK - siga para J1.2` → tudo deu certo; siga.
- `>>> J1.1 FALHOU - pare e leia o erro acima` → um comando falhou e **os
  seguintes não rodaram**. Não siga: veja o "Se falhar" do bloco.

Os comandos do `lab.py` também terminam com `RESULTADO: OK`,
`RESULTADO: FALHOU` ou `RESULTADO: CANCELADO` (você não digitou a confirmação;
nada foi alterado). Cole um bloco por vez.

| Ação | bash / PowerShell 7 | Windows PowerShell 5.1 |
|---|---|---|
| Variável de ambiente | `export EVIDENCE_RUN_ID=run-$(date -u +%Y%m%d)` | `$env:EVIDENCE_RUN_ID = "run-" + (Get-Date).ToUniversalTime().ToString("yyyyMMdd")` |
| Capturar output | `ENV_ID=$(terraform -chdir=infra/terraform output -raw environment_id)` | `$ENV_ID = terraform -chdir=infra/terraform output -raw environment_id` |
| Hora UTC | `date -u +%Y-%m-%dT%H:%M:00Z` | `(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:00Z")` |

## Contas e credenciais (uma vez por conta)

Contas criadas com login do Google (ou outro SSO) funcionam normalmente.

1. **Aiven — token.** No console da Aiven: menu do usuário → **Tokens** →
   **Generate token**. Anote também o nome técnico do projeto. A Aiven não
   exige login no terminal: o token basta.
2. **Confluent — login na CLI** (repita em cada Codespace/máquina novo):

   ```bash
   confluent login --no-browser
   ```

   Digite o e-mail. Contas Google/SSO **não pedem senha**: a CLI mostra um
   link — abra no navegador do seu computador, entre e cole o código exibido.
   Deu certo se aparecer `Logged in as "..."`. Se pedir senha numa conta
   Google, o e-mail foi digitado errado: pressione Enter e repita.
3. **Confluent — Cloud API key** (para o Terraform). Crie pela CLI, já logada —
   assim ela é do tipo certo (*Cloud*, não de cluster):

   ```bash
   confluent api-key create --resource cloud --description terraform-desafio
   ```

   Copie `API Key` e `API Secret` para o `.env` (passo 4) e depois rode
   `clear` para tirar o segredo da tela. O segredo só aparece nesse momento.
4. **`.env`:** `cp .env.example .env` e preencha **só** `AIVEN_TOKEN`,
   `TF_VAR_aiven_project`, `CONFLUENT_CLOUD_API_KEY` e
   `CONFLUENT_CLOUD_API_SECRET` (sem aspas nem espaços). Todo o resto é gerado
   pelos scripts — **não preencha senhas do CDC**.

> **Sempre que criar uma chave nova, atualize o `.env`** com o novo par e
> apague a chave antiga no console (Administration → API keys). Se você usa
> **Codespaces secrets** com esses nomes, eles vencem o `.env`: atualize-os em
> github.com/settings/codespaces ou apague-os.

**Por que duas credenciais da Confluent?** A API key do `.env` é usada pelo
**Terraform** para criar e destruir recursos. A **CLI** usa a sua sessão de
usuário para consultas e para o Flink — listar ACLs, conectores e statements,
rodar SQL e ler o billing.

Opcional: cloud/região/nomes da Confluent são variáveis Terraform
(`TF_VAR_confluent_cloud`, `TF_VAR_confluent_region`, padrão `AWS`/`us-east-1`).

---

## J0 — Verificação (sem custo; repetir é seguro)

**J0.1 — Código e `.env`**

```bash
python lab.py setup &&                    # terraform init + validate + CLIs
python lab.py test &&                     # testes locais (mais de 270)
python -m scripts.check_configuration foundation &&
echo ">>> J0.1 OK - siga para J0.2" || echo ">>> J0.1 FALHOU - pare e leia o erro acima"
```

**Se falhar:** `MISSING_KEYS=...` → preencha essas variáveis no `.env` e repita.
Menos de 270 testes ou `scripts.check_configuration` inexistente → branch
antiga: volte ao passo de Ambiente.

**J0.2 — Credenciais funcionam e conta está vazia**

```bash
python scripts/check_cloud_credentials.py &&   # as chaves do .env funcionam
python scripts/check_clean_slate.py &&         # nada de tentativas anteriores na nuvem
confluent billing promo list &&                # créditos (e confirma o login da CLI)
export EVIDENCE_RUN_ID=run-$(date -u +%Y%m%d) &&
echo ">>> J0.2 OK - siga para J1.1" || echo ">>> J0.2 FALHOU - pare e leia o erro acima"
```

**Se falhar:**
- `CONFLUENT_CREDENTIALS=FAILED HTTP=401` → a chave não é uma Cloud API key
  válida: refaça o passo 3 de Contas.
- `_SOURCE=CONFLICT` → uma variável do ambiente (Codespaces secret, perfil)
  tem outro valor e vence o `.env`: `unset <VARIÁVEL>` e apague/atualize o secret.
- `_SOURCE=DOTENV` e 401 → chave recém-criada leva 1–2 min para valer.
- `AIVEN_CREDENTIALS=FAILED` → confira o token e o nome do projeto.
- `CONFLICT environment|service_account|aiven_service ...` → restos de uma
  tentativa anterior que ficaram na nuvem fora do State; cada linha traz o
  comando para remover (`NEXT_ACTION`). Remova e repita o bloco.
- `STATE_NOT_EMPTY=True` → você está retomando uma execução já iniciada; a
  checagem é pulada de propósito.

**Windows:** variáveis `PG*` gravadas no perfil do usuário bloqueiam o J2
(`POSTGRES_ENV_CONFLICT`); remova-as antes.

## J1 — Fundação e recursos permanentes

**J1.1 — Fundação** (environment, cluster Kafka Basic, Schema Registry,
5 identidades e suas chaves: 14 recursos)

```bash
python lab.py plan &&
python lab.py review-plan &&                 # CREATE_COUNT=14 (ou só os que faltam)
python lab.py apply --confirm-foundation &&  # digite APPLY FOUNDATION
echo ">>> J1.1 OK - siga para J1.2" || echo ">>> J1.1 FALHOU - pare e leia o erro acima"
```

**J1.2 — Variáveis geradas**

```bash
python -m scripts.export_foundation_env &&
python -m scripts.check_configuration pipeline &&
echo ">>> J1.2 OK - siga para J1.3" || echo ">>> J1.2 FALHOU - pare e leia o erro acima"
```

**J1.3 — Pipeline** (Postgres Aiven, compute pool Flink, identidades do Flink
e de métricas, role bindings: 16 recursos)

```bash
python lab.py plan-pipeline &&
python lab.py review-plan --pipeline &&             # mostra CREATE_COUNT=16
python lab.py apply-pipeline --confirm-pipeline &&  # digite APPLY PIPELINE
echo ">>> J1.3 OK - siga para J2" || echo ">>> J1.3 FALHOU - pare e leia o erro acima"
```

**Se um bloco falhar:** corrija a causa (o erro está acima do `FALHOU`) e
**repita o bloco inteiro**. Isso é seguro em todo o roteiro: planos de
tentativas anteriores são descartados (`PREVIOUS_PLAN_DISCARDED`), arquivos de
tentativas anteriores são arquivados (`PREVIOUS_ATTEMPT_ARCHIVED`) e, se um
apply criou só parte dos recursos, o novo plano cria apenas o que falta — os
gates continuam recusando qualquer update/destroy inesperado.
Depois do J1.3 **não rode `plan-pipeline` de novo**: as etapas seguintes têm
scripts próprios.

## J2 — Origem PostgreSQL

O Postgres leva alguns minutos para ficar `RUNNING`. Se o primeiro comando
falhar por isso, espere 2–3 min e repita o bloco.

```bash
python scripts/export_postgres_env.py &&
python scripts/fetch_aiven_ca.py &&
python scripts/bootstrap_postgres.py apply &&     # schema, publicação e seed
python scripts/configure_cdc_user.py --apply &&   # cria cdc_user e grava a senha no .env
python -m scripts.check_configuration cdc &&      # mostra CDC_PASSWORD_MATCH=True
python scripts/preflight_postgres_cdc.py &&
echo ">>> J2 OK - siga para J3" || echo ">>> J2 FALHOU - pare e leia o erro acima"
```

Na saída: contagens 200/240/320/60/2000 e `CDC_PREFLIGHT_GATE= PASS`.
`POSTGRES_ENV_CONFLICT:<VAR>` → uma variável `PG*` do ambiente difere do `.env`;
remova-a (`unset <VAR>`) e repita.

## J3 — Permissões Kafka (ACLs)

```bash
python scripts/plan_cdc_acls.py &&                # 11 ACLs esperadas
python scripts/apply_cdc_acls.py --confirm-acls &&
ENV_ID=$(terraform -chdir=infra/terraform output -raw environment_id) &&
KAFKA_ID=$(terraform -chdir=infra/terraform output -raw kafka_cluster_id) &&
confluent kafka acl list --environment $ENV_ID --cluster $KAFKA_ID &&
echo ">>> J3 OK - siga para J4" || echo ">>> J3 FALHOU - pare e leia o erro acima"
```

A lista deve ter 14 ACLs (11 novas + 3 do Flink). `ENV_ID` e `KAFKA_ID` valem
para este terminal; num terminal novo, repita as duas linhas.

---

## J4 — Janela faturável (≤ 2 h a partir daqui)

**Condições de parada** — se qualquer uma ocorrer, vá direto ao J5
(fechamento) e investigue com tudo desligado: apply do conector falhou;
conector fora de `RUNNING` após 10 min; statement Flink `FAILED`; alerta não
observado em 10 min; janela chegou a 2 h.

**J4.1 — Ingestão (CDC)**

```bash
WINDOW_START=$(date -u +%Y-%m-%dT%H:%M:00Z) &&
python scripts/plan_cdc_connector.py &&
python scripts/apply_cdc_connector.py &&
echo "Aguardando o conector ficar RUNNING (até 10 min)..." &&
for i in $(seq 20); do confluent connect cluster list --environment $ENV_ID --cluster $KAFKA_ID | grep -q RUNNING && break; sleep 30; done &&
confluent connect cluster list --environment $ENV_ID --cluster $KAFKA_ID | grep RUNNING &&
sleep 60 &&                                        # snapshot inicial
python src/consumer/audit_cdc.py &&                # 6 tópicos lidos
python scripts/cdc_test_scenario.py --execute &&   # baseline + INSERT/UPDATE/DELETE + verificação
echo ">>> J4.1 OK - siga para J4.2" || echo ">>> J4.1 FALHOU - pare e leia o erro acima"
```

Na saída: `LIFECYCLE_GATE= PASS` com `C`, `U`, `D` e `TOMBSTONE`.
**Se o apply do conector falhar:** veja se ficou conector órfão
(`confluent connect cluster list ...`). Para diagnosticar sem custo:
`python scripts/validate_cdc_connector_config.py` (valida campo a campo, sem
criar nada) e, depois de um novo `plan_cdc_connector.py`,
`python scripts/apply_cdc_connector.py --show-error` (erro mascarado na tela).

**J4.2 — Contrato (Schema Registry)**

```bash
python scripts/plan_schema_compatibility_policy.py &&
python scripts/apply_schema_compatibility_policy.py &&
python scripts/verify_schema_compatibility.py &&   # opcional aceito, obrigatório rejeitado
python scripts/collect_schema_evidence.py &&
echo ">>> J4.2 OK - siga para J4.3" || echo ">>> J4.2 FALHOU - pare e leia o erro acima"
```

**J4.3 — Processamento (Flink SQL)**

```bash
python lab.py flink-setup &&                        # preflight: 3 passos MISSING
python lab.py flink-setup --apply &&                # digite APPLY FLINK
python scripts/validate_temporal_join.py &&         # STAGE9_DATA_GATE= PASS
python -m scripts.fraud_stream start --confirm-start &&
sleep 30 &&
python -m scripts.fraud_stream status &&            # STATEMENT_PHASE=RUNNING
python -m scripts.fraud_scenarios execute --confirm-execute &&   # espera o alerta (até 10 min)
python -m scripts.fraud_stream inspect-null &&
echo ">>> J4.3 OK - siga para J4.4" || echo ">>> J4.3 FALHOU - pare e leia o erro acima"
```

Na saída: `ALERT_CONFIRMATION=PASS`, `FRAUD_SEQUENCE_MATCHED=True` e
`LEGITIMATE_IN_ANY_MATCH=False`.

**J4.4 — Operação (métricas e inventário)** — espere ~5 min depois do J4.3
(latência da Metrics API).

```bash
python scripts/collect_metrics_evidence.py --start $WINDOW_START &&
TODAY=$(python -c "import datetime as d; print(d.datetime.now(d.timezone.utc).date())") &&
TOMORROW=$(python -c "import datetime as d; print(d.datetime.now(d.timezone.utc).date() + d.timedelta(1))") &&
python -m scripts.collect_operations_evidence collect --confirm-read --start-date $TODAY --end-date $TOMORROW --environment $ENV_ID --cluster $KAFKA_ID &&
echo ">>> J4.4 OK - siga para J5" || echo ">>> J4.4 FALHOU - pare e leia o erro acima"
```

`METRICS_STATUS=SEM_DADOS` → repita só o primeiro comando em 10 min.

## J5 — Fechamento da janela

```bash
python scripts/teardown_cdc_connector.py --execute &&
confluent connect cluster list --environment $ENV_ID --cluster $KAFKA_ID &&   # None found.
echo ">>> J5 OK - siga para J6" || echo ">>> J5 FALHOU - pare e leia o erro acima"
```

## J6 — Teardown total

```bash
python lab.py teardown --confirm-destroy &&   # revise DESTROY_COUNT e FLINK_STATEMENTS_TO_DELETE; digite DESTROY PIPELINE
test -z "$(terraform -chdir=infra/terraform state list)" &&
confluent environment list > /tmp/envs.txt &&
! grep -q desafio-final /tmp/envs.txt &&
confluent iam service-account list > /tmp/sas.txt &&
! grep -qE "desafio-|payment-fraud-" /tmp/sas.txt &&
echo ">>> J6 OK - tudo derrubado" || echo ">>> J6 FALHOU - pare e leia o erro acima"
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
| Um bloco falhou | Corrija a causa e repita o bloco inteiro: planos antigos são descartados, arquivos de tentativas anteriores arquivados e applies parciais completados só com o que falta. |
| `CONFLICT ...` no J0.2 | Restos fora do State; rode o `NEXT_ACTION` de cada linha e repita o J0.2. |
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
