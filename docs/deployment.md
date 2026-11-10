# Implantação e portabilidade

## Ambientes suportados como objetivo de projeto

O executor pode ser um terminal Linux, macOS, Windows ou ambiente remoto que disponha das ferramentas exigidas. **Codespaces é opcional**, não é parte da arquitetura. O repositório contém um `.devcontainer/` como conveniência; testes locais em um sistema operacional não provam compatibilidade universal.

O processamento real depende de serviços externos da **Aiven** e da **Confluent Cloud**, além de permissões e orçamento. Uma implantação integral sem serviços externos não está implementada neste repositório.

## Ferramentas e preparação

- Git; Python **3.12+**; Terraform **1.16+**; Confluent CLI **4.81+**, conforme verificações de `lab.py`.
- Instalar dependências Python a partir de `requirements.txt`, preferencialmente em ambiente virtual. No Windows usar o Python do `.venv\Scripts\python.exe`; em Linux/macOS usar o Python do ambiente virtual ativado.
- Validar versões e sintaxe: `python lab.py setup` e `python lab.py check-cli`. `setup` executa `terraform init`, `terraform validate` e checagens de CLI, mas não provisiona recursos.
- Executar `python lab.py test` antes de qualquer operação com nuvem.

## Configurações essenciais

Não versionar `.env`. Usar variáveis de ambiente e/ou `.env` local não publicado. `AIVEN_TOKEN`, `CONFLUENT_CLOUD_API_KEY`, `CONFLUENT_CLOUD_API_SECRET` são credenciais de provedores. O Terraform exige também `TF_VAR_aiven_project` e `TF_VAR_aiven_pg_service_name`, que identificam um **projeto Aiven pré-existente** e o nome desejado do serviço PostgreSQL. O recurso `aiven_pg.payments` cria o serviço, **não cria a conta nem o projeto Aiven**.

Os acessos de Kafka/Schema Registry e as variáveis `TF_VAR_foundation_*` podem ser disponibilizados após o primeiro provisionamento via `scripts/export_foundation_env.py`. Não imprimir segredos ou conteúdo bruto de State e planos.

## Sequência lógica e pontos de controle

| Fase | Ação verificada no código | Controle |
|---|---|---|
| Preparação | `python lab.py setup`; `python lab.py test` | Sem provisionamento remoto |
| Plano inicial | `python lab.py plan` | Salva `foundation.tfplan`; revisar antes de aplicar |
| Foundation | `python lab.py apply --confirm-foundation` | Requer revisão/aceite interativo e allowlist de recursos |
| Infraestrutura completa | `python lab.py plan-pipeline`; `python lab.py review-plan --pipeline` | Plano salvo com mudanças permitidas; revisar custos |
| Aplicação completa | `python lab.py apply-pipeline --confirm-pipeline` | Operação remota sujeita a confirmação; se incluir CDC requer também `--allow-cdc` |
| Origem | `python scripts/bootstrap_postgres.py check` | Somente verificação; `apply` modifica DDL/seeds |
| Flink | `python lab.py flink-setup` | Preflight; `--apply` executa DDLs mediante confirmação |
| Regra contínua | `python -m scripts.fraud_stream plan` | Antes de `start --confirm-start` |
| Cenários | `python -m scripts.fraud_scenarios plan` | Antes de `execute --confirm-execute` |

**Atenção:** essa tabela mapeia interfaces verificadas no código, **não é promessa de execução automatizada integral em um único comando**. Dependências entre fases, identidade ativa no CLI, permissões, replicação lógica, origem Kafka e orçamento devem ser conferidos em cada gate. `plan-pipeline` e `apply-pipeline` foram desenhados para bloquear operações inseguras; jamais burlar essas proteções para concluir a demonstração.

## Verificação e encerramento

Depois da implantação, comprovar a existência de recursos na conta correta, os cinco tópicos de tabelas e os eventos CDC. Para o Flink, registrar statements, estados e correspondências produzidas. Ao encerrar, consultar [operação e teardown](operations.md); não excluir o State local antes de verificar a destruição remota.

## Limitantes de portabilidade conhecidos

O README e alguns comentários históricos ainda mencionam Codespaces e versões internas. Isso precisa ser saneado na revisão editorial final. A compatibilidade operacional completa em Windows, Linux e macOS exige execução dos respectivos procedimentos de bootstrap/CLI em cada plataforma; não está comprovada apenas pelos testes unitários.
