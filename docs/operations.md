# Operação, segurança e custos

## Responsabilidades

O operador escolhe o projeto/conta e as regiões, autoriza operações faturáveis, verifica os recursos provisionados e conserva o State com segurança. As ACLs e identidades são declaradas em `infra/terraform/`; a presença do código não prova aplicação remota.

## Controles existentes

- `lab.py` separa `plan`, revisão, `apply` confirmado, preparação Flink e `teardown` confirmado.
- `scripts/plan_cdc_connector.py` cria um plano que só aceita a criação isolada do conector esperado; `scripts/apply_cdc_connector.py` recusa alterações extras.
- `scripts/teardown_cdc_connector.py` permite destruição controlada do conector.
- `scripts/collect_operations_evidence.py` coleta inventário e custos por contexto de ambiente; a sanitização e atribuição por ambiente exigem revisão humana.
- `evidencias/billing/` contém uma exportação histórica; não assume faturamento atual nem valores gratuitos.

## Janela operacional

1. Confirmar conta, ambiente, State e recursos antes de criar o conector CDC.
2. Planejar a criação e revisar ações/custos; executar apenas após autorização explícita.
3. Monitorar saúde do conector, fluxo CDC, tópicos e estado dos statements Flink.
4. Executar dados sintéticos e coletar evidências sanitizadas sem expor identificadores sensíveis.
5. Encerrar o processamento contínuo desnecessário e destruir o conector conforme seu plano controlado.
6. Confirmar remotamente ausência de recursos faturáveis indesejados e consultar billing novamente.

## Teardown completo

`python lab.py teardown --confirm-destroy` **planeja e, após confirmação interativa, destrói todos os recursos do State atual**. É uma ação potencialmente irreversível. Usá-la apenas quando o ambiente completo puder ser eliminado; não confundir com a retirada isolada do conector. O script não substitui verificação remota posterior.

Não remover `.terraform`, arquivos de State ou o ambiente de execução antes de confirmar que os recursos externos foram encerrados. Não anexar State nem planos `.tfplan` a issues, pull requests ou evidências.

## Evidências operacionais

Cada comprovação deve registrar: data/hora, ambiente, comando, operação executada, resultado, identificadores sanitizados, custo/consumo quando disponível e status do teardown. Ausência de alertas observados deve permanecer descrita como pendência de validação, não como sucesso implícito.
