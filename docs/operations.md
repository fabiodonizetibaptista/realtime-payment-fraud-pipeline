# Operação, segurança e custos

Comandos: [runbook.md](runbook.md). Aqui ficam as regras de operação.

## Responsabilidades do operador

Escolher conta, projeto e região; definir o teto de custo antes da janela
(recomendado: US$ 5 e 2 h); autorizar cada etapa faturável; conservar o State
local até a verificação remota do teardown; nunca publicar `.env`, State ou
planos.

## Controles no código

- Cada etapa só aplica o que o seu gate espera: `lab.py` (fundação com 14
  creates, pipeline sem destroy/update), `plan/apply_cdc_acls.py` (exatamente
  as 11 ACLs), `plan/apply_cdc_connector.py` (só o conector),
  `plan/apply_schema_compatibility_policy.py` (só a política).
- Planos submetidos ao apply são apagados automaticamente (consumidos ou
  obsoletos) e nunca reutilizados.
- Falhas do conector são classificadas (`.local/diagnostics/`) sem gravar o
  texto do provider; `--show-error` mostra o erro mascarado só na tela.
- `lab.py teardown` lista os statements Flink na revisão, apaga-os depois da
  confirmação e só então destrói os recursos do State. As ACLs e a política do
  Schema Registry dependem explicitamente das credenciais que as gerenciam, o
  que garante a ordem ACL → chave → role binding → cluster → environment.
- `scripts/reconcile_state.py` reconcilia o State com a nuvem se um teardown
  falhar no meio (nunca repita o teardown às cegas).
- Coleta de evidência com escopo explícito: `collect_operations_evidence.py`
  (`--environment/--cluster`) e `collect_metrics_evidence.py` (identidade
  `desafio-metrics`, chave lida do State só em memória).

## Janela faturável

O conector CDC e os statements Flink são o que cobra por hora. Eles existem só
entre o J4 e o J5 do roteiro. Condições de parada (encerrar a janela e
investigar com tudo desligado): apply do conector falhou; conector fora de
`RUNNING` em 10 min; statement `FAILED`; alerta não observado em 10 min;
janela de 2 h atingida.

## Teardown

`python lab.py teardown --confirm-destroy` destrói **tudo** o que está no State
atual, depois de mostrar `DESTROY_COUNT` e `FLINK_STATEMENTS_TO_DELETE` e pedir
`DESTROY PIPELINE`. Em seguida, confirme: `state list` vazio, nenhum
`desafio-final` em `confluent environment list`, nenhuma service account
`desafio-*`/`payment-fraud-*` e nenhum `payments-postgres` no console da Aiven.

## Custos

O billing da Confluent aparece com 24–72 h de atraso. Registre o custo como
parcial até que todos os dias da janela tenham linhas em
`confluent billing cost list`. `evidencias/billing/` guarda uma exportação de
execução anterior e não representa a execução atual.

## Evidências

Com `EVIDENCE_RUN_ID` definido, cada execução grava em
`evidencias/runs/<id>/` sem sobrescrever as anteriores. Registrar: data/hora,
comando, resultado, identificadores sem segredo e situação do teardown.
Ausência de alerta é pendência, não sucesso.
