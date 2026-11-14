# Etapa 4 — Plano de teardown do conector CDC

## Proveniência

Documento formalizado retrospectivamente após a primeira janela
de execução da V2. Não constitui evidência de que este documento
existia antes daquela janela.

## Recurso faturável autorizado

- Recurso Terraform: `confluent_connector.payments_cdc[0]`
- Conector gerenciado: `payments-cdc-aiven`
- Condição de encerramento: após o gate operacional ou falha de teste

## Procedimento de encerramento

1. Executar `python scripts/teardown_cdc_connector.py --execute`.
2. Confirmar `ONLY_CONNECTOR_DELETE=True`.
3. Confirmar `TERRAFORM_APPLY_SUCCESS=True`.
4. Confirmar `CONNECTOR_ABSENT_FROM_STATE=True`.
5. Confirmar `TEARDOWN_GATE=PASS`.
6. Quando necessário, confirmar a exclusão também na API da Confluent.

## Recursos preservados

- PostgreSQL Aiven e dados das tabelas
- Kafka cluster e tópicos
- Service Accounts, API Keys e ACLs
- Demais recursos da Foundation

## Limites

O teardown remove exclusivamente o conector Terraform.
Não comprova a remoção do replication slot PostgreSQL.
Nenhuma exclusão adicional é autorizada por este documento.

## Próximas janelas

Este plano deve ser consultado e registrado ANTES de criar
o conector, juntamente com a autorização para a janela.
