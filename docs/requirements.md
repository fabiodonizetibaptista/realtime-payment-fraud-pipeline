# Requisitos e critérios de aceite

Este documento sintetiza os requisitos do desafio de pipeline de pagamentos em tempo real. A referência de avaliação é **o comportamento demonstrado do pipeline**, não a sequência histórica de desenvolvimento nem os nomes dos recursos usados no exemplo do instrutor.

## Objetivo

Construir e documentar um fluxo reproduzível de pagamentos sintéticos: **PostgreSQL → CDC (Debezium) → Confluent Cloud/Kafka (Avro) → Flink SQL (enriquecimento e detecção) → alerta disponível para consumo**.

## Matriz de requisitos

| Camada | Requisito funcional | Evidência mínima para demonstrar |
| --- | --- | --- |
| Fundação | Provisionar ambiente e cluster Kafka e separar identidades de escrita e leitura, com permissões mínimas | Inventário dos recursos e das permissões de cada identidade, sem divulgar credenciais |
| Contratos | Registrar schemas Avro no Schema Registry e testar uma evolução compatível e outra incompatível | Resultado da verificação de compatibilidade: alteração aceita e alteração rejeitada |
| Ingestão | Capturar alterações do PostgreSQL via CDC; demonstrar INSERT, UPDATE e DELETE como eventos Kafka | Eventos correlacionáveis com alterações da origem, incluindo operação e comportamento de exclusão |
| Processamento | Enriquecer transações com dados de contas usando Flink SQL e detectar **três transações do mesmo cartão em até 60 segundos** | Consulta/statement executado, correspondências reais e rastreabilidade dos eventos que originaram o alerta |
| Operação | Apresentar observabilidade, controles de acesso, custo e confiabilidade do fluxo | Métricas/diagnósticos, relação entre identidades e permissões, extrato de billing e limitações conhecidas |
| Entrega | Disponibilizar repositório reproduzível e documentado | README com arquitetura, decisões técnicas, instruções de implantação, validação, evidências e encerramento seguro dos recursos |

## Critérios de conclusão

1. As camadas devem ter arquivos de configuração e SQL versionados, acompanhados de evidências de execução compatíveis com o requisito.
2. O procedimento de implantação deve partir de pré-requisitos explícitos e não depender de IDs, credenciais ou recursos ocultos de execuções anteriores.
3. Deve ser possível relacionar um alerta aos eventos sintéticos de origem; a mera existência de SQL ou de um statement não comprova essa relação.
4. O repositório não deve conter senhas, tokens, arquivos `.env` privados ou Terraform State/plan sensíveis.
5. A documentação deve registrar os custos observados e o procedimento de teardown, com confirmação remota dos recursos encerrados.

## Delimitação de escopo

- **Requisitos:** os itens acima são derivados da descrição e das cinco camadas do desafio.
- **Exemplos, não imposições:** nomes exatos de contas, tópicos, serviços, provedores PostgreSQL e scripts presentes no material de referência do instrutor podem ser substituídos por implementações equivalentes, desde que o comportamento seja demonstrado.
- **Evoluções opcionais:** regras adicionais de fraude, dead-letter queue, Iceberg/Tableflow, modelos de IA e mudança de domínio não são pré-requisitos para o fluxo central.
- **Limitação importante:** a presença de código, testes locais ou parecer de auditoria não substitui a evidência de execução integrada no ambiente remoto.

## Onde localizar a implementação

Consulte `README.md` para arquitetura e operação, `infra/terraform/` para a infraestrutura, `schemas/registry/` para os contratos, `database/` para a origem, `sql/` para o processamento, `scripts/` para automações, `tests/` para testes e `evidencias/` para registros de execução.
