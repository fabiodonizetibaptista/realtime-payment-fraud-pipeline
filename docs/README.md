# Documentação técnica

Comece pelo [README principal](../README.md) (camadas, evidências e custo) e
use o **[roteiro de execução](runbook.md)** para subir e derrubar o pipeline —
ele é a única fonte de comandos.

## Reprodução e operação

- [Roteiro de execução (J0–J7)](runbook.md)
- [Implantação e portabilidade](deployment.md)
- [Instalação das ferramentas em máquina própria](local-bootstrap.md)
- [Operação, segurança e custos](operations.md)
- [Consultas da Metrics API](observability/README.md)

## Arquitetura e contratos

- [Arquitetura e decisões técnicas](architecture.md)
- [Requisitos e critérios de aceite](requirements.md)
- [Decisões de origem PostgreSQL e CDC](decisions/postgres-cdc.md)
- [Contrato de alertas e watermark](alert-contract.md)

## Validação

- [Matriz de validação](validation.md)
- [Regra de detecção](validation/fraud-pattern.md)
- [Processamento contínuo](validation/fraud-stream.md)
- [Cenários sintéticos](validation/fraud-scenarios.md)
- [Recursos, segurança e custos](validation/operations.md)
- [Metadados da tabela Flink de contas](validation/flink-table-metadata.md)
- [Prontidão para reprodução (gates)](audits/reproduction-readiness-backlog.md)

As evidências sanitizadas ficam em `evidencias/`; as de cada execução
completa, em `evidencias/runs/<id>/`.
