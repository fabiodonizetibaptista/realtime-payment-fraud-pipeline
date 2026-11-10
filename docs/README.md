# Documentação técnica

Esta documentação descreve o **estado implementado** do pipeline e diferencia
resultados históricos observados de validação operacional ainda não comprovada.

## Arquitetura e contratos

- [Requisitos e critérios de aceite](requirements.md)
- [Decisões de origem PostgreSQL e CDC](decisions/postgres-cdc.md)
- [Contrato de alertas e watermark](alert-contract.md)

## Evidências de execução e validação

- [Metadados da tabela Flink de contas](validation/flink-table-metadata.md)
- [Regra de detecção e testes locais](validation/fraud-pattern.md)
- [Processamento contínuo](validation/fraud-stream.md)
- [Cenários sintéticos e rastreabilidade](validation/fraud-scenarios.md)
- [Recursos, segurança e custos](validation/operations.md)

Os arquivos de `evidencias/` contêm registros sanitizados separados por
componente. Eles não são substitutos automáticos de evidências de alerta
ponta a ponta: consulte o status explícito de cada validação.

Para executar testes locais, utilize `python3 lab.py test` conforme o
[README principal](../README.md). Qualquer operação remota potencialmente
faturável deve ser planejada e autorizada separadamente.
