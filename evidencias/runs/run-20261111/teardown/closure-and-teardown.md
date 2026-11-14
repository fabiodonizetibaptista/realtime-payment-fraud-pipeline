# Fechamento e teardown (run-20261111)

Janela faturável: conector `RUNNING` de 2026-11-12T01:57Z a ~02:55Z (≈1 h).

## Fechamento da janela

```text
STATEMENTS_TO_DELETE=44
...
Deleted Flink SQL statement "etapa11-fraud-pattern-matches".
========== CDC TEARDOWN ==========
PLANNED_CHANGES= 1
ONLY_CONNECTOR_DELETE= True
TERRAFORM_APPLY_SUCCESS= True
CONNECTOR_ABSENT_FROM_STATE= True
TEARDOWN_GATE= PASS
$ confluent connect cluster list ...
None found.
$ confluent flink statement list ...
None found.
```

## Teardown total — o que aconteceu (registro honesto)

1. `lab.py teardown` planejou `DESTROY_COUNT=39` e **falhou no meio**: as ACLs
   autenticam com a chave admin passada ao provider por variável, então o
   Terraform não sabia que dependiam dela e destruiu chave e environment
   antes; 6 ACLs receberam `401` e 4 service accounts ficaram presas.
2. O refresh do State não era possível (a credencial já não existia). Como o
   cluster dono das ACLs comprovadamente não existia mais, as 6 ACLs foram
   removidas do State (`terraform state rm`, uma vez, autorizado e após
   verificação remota).
3. Novo `lab.py teardown`: `DESTROY_COUNT=4`, `TEARDOWN_COMPLETED=True`.
4. Correção no código: `depends_on` da chave admin em todas as ACLs e da chave
   do Schema Registry na política (commit `8b1cfd9`), com teste de regressão.

## Verificação remota final

```text
$ terraform -chdir=infra/terraform state list
(vazio)
$ confluent environment list
  Current |     ID     |  Name   | Stream Governance Package
          | env-53kdnq | default | ESSENTIALS
$ confluent iam service-account list
          | sa-wzwz2d5 | SA_Teste |
```

`default` e `SA_Teste` são da conta, não do projeto. Nenhum recurso
`desafio-*`/`payment-fraud-*` restou.
