# Backlog de correções — Reprodução independente

**Projeto:** `realtime-payment-fraud-pipeline`
**Data de abertura:** 2026-11-09
**Branch de referência da auditoria independente:** `chore/project-finalization`
**Commit de referência informado:** `bb106a4` — confirmar SHA completo no Git ao iniciar a correção
**Branch proposta para correções:** `fix/reproduction-readiness`
**Situação da auditoria independente:** levantamento inicial, sem provisionamento informado.

## Objetivo e regras de execução

Registrar e resolver de modo rastreável as lacunas encontradas por um avaliador independente ao tentar reproduzir o pipeline a partir de um ambiente limpo. Este documento **não é evidência de execução ponta a ponta**, nem confirma correção de nenhum item.

- **Preservar** a branch e o commit examinados pelo auditor na primeira tentativa; não realizar correções silenciosas na referência auditada.
- Trabalhar em `fix/reproduction-readiness`, criada a partir da referência exata auditada, com commits pequenos e testes de regressão.
- Não executar provisionamento, testes com serviços cobrados ou teardown na auditoria documental sem autorização explícita.
- Não publicar tokens, segredos, `.env`, Terraform State, planos binários ou outputs sensíveis.
- Para cada item: guardar evidência de falha, mudança concreta, teste, revisão e referência do commit de correção.
- Se for detectado segredo **ativo** exposto, interromper o fluxo de publicação e tratar rotação, revogação e alcance no histórico Git imediatamente.
- Ao concluir, entregar relatório do que está **corrigido**, **validado localmente**, **validado em nuvem** e **não comprovado**, sem confundir essas categorias.

## Matriz de lacunas

| ID | Lacuna reportada pelo auditor | Classificação atual | Prioridade | Correção/validação esperada | Critério de aceite | Estado |
|---|---|---|---|---|---|---|
| L1 | README tem caracteres corrompidos, como `compat?vel`, `vers?o` e `reposit?rio`. | **Confirmada** por inspeção anterior | P1 | Restaurar texto UTF-8 e conferir títulos, comandos e caracteres acentuados. | README legível em GitHub e no terminal; teste/editorial sem sequências corrompidas relevantes. | ABERTO |
| L2 | README diz que Codespaces é opcional, mas existe `.devcontainer/`. | **Não é contradição por si só**; capacidade de bootstrap ainda requer teste | P3 | Confirmar que Codespaces é alternativa opcional e que a instalação do Dev Container funciona. | Pré-requisitos claros para ambiente local/remoto; validação do Dev Container registrada sem exigir Codespaces como dependência do produto. | A VERIFICAR |
| L3 | README não apresenta o comando explícito para executar o `apply` Terraform. | **Confirmada no README** | P1 | Documentar sequência e comandos existentes (`plan`, revisão, `apply` de foundation/pipeline), parâmetros, gates, escopo das mutações e cautelas de custo. **Conferir flags no código atual antes de publicar.** | Usuário novo consegue localizar comando correto e pré-condições sem adivinhar; documentação bate com `lab.py --help`. | ABERTO |
| L4 | README não apresenta comandos exatos para Flink contínuo e simulação de fraude. | **Confirmada no README** | P1 | Explicitar comandos reais para preparação Flink, início/estado/inspeção do stream e execução de cenários sintéticos; citar pré-condições e efeito remoto. **Conferir interfaces na branch congelada.** | Comandos copiados da documentação são aceitos pelas interfaces CLI; sequência inclui verificação do alerta e não declara sucesso sem observação real. | ABERTO |
| L5 | README não informa comando exato de teardown do conector CDC. | **Confirmada no README** | P1 | Especificar procedimento de encerramento, confirmação de ausência do conector, escopo de recursos e segurança de Terraform State; separar teardown do conector de teardown geral. | Operador identifica e testa o procedimento com gates apropriados; nenhum recurso não pertencente à execução é destruído. | ABERTO |
| L6 | Falta orientação suficiente para criar/configurar contas, autenticação, permissões e créditos da Aiven/Confluent. | **Parcialmente documentada; lacuna de onboarding confirmada** | P2 | Documentar pré-requisitos manuais, projeto Aiven vs PostgreSQL provisionado, criação de organização Confluent, autenticação CLI, perfis/permissões mínimas, armazenamento de secrets, billing e limites de custo. | Usuário novo identifica dependências externas e o que executar manualmente; sem segredos em logs; links oficiais atuais verificados. | ABERTO |
| L7 | Mínimos Terraform `1.16+` e Confluent CLI `4.81+` exigem conferência real. | **Versões reportadas como existentes; compatibilidade operacional não comprovada** | P2 | Conferir versão requisitada no README, instalador do Dev Container, lockfiles e releases oficiais; testar instalação e comandos `--help` em ambiente limpo. | Pré-requisitos e instalador consistentes, com resultados registrados; sem alegação de suporte universal não testado. | A VERIFICAR |
| L8 | `evidencias/` contém dados de execuções anteriores (identificadores, presença de credenciais e billing); verificar exposição. | **Arquivos versionados confirmados; vazamento não demonstrado** | P0 caso segredo ativo; senão P2 | Auditar conteúdo dos arquivos e histórico Git, classificar identificadores, sanitizar/remover apenas o necessário, manter evidências úteis com origem clara; migrar `evidencias/etapa-9/` para organização funcional, atualizando referências. | Ausência de segredos ativos confirmada por revisão adequada; evidências rastreáveis e classificadas; diretório histórico resolvido sem perder prova. | A VERIFICAR |

**Legenda:** P0 = risco de segurança imediato; P1 = dificulta ou bloqueia reprodução; P2 = risco relevante de operação/documentação; P3 = melhoria ou validação não bloqueante.

## Pacotes de execução

### Pacote A — Documentação operacional (L1, L3, L4, L5)

1. Confirmar comandos e flags a partir do código versionado e da ajuda CLI real, **antes** de editar o texto.
2. Corrigir codificação do README e as seções de implantação, Flink, simulação e teardown.
3. Criar/verificar testes de integridade de links e comandos documentados sem executar serviços faturáveis.
4. Registrar commit, número de testes e evidências de revisão.

### Pacote B — Contas, portabilidade e versões (L2, L6, L7)

1. Validar `.devcontainer` em ambiente limpo; não confundir Codespaces opcional com dependência.
2. Documentar fluxo de cadastro e permissões Aiven/Confluent e autenticação Confluent CLI.
3. Verificar versões realmente instaladas, instalador, compatibilidade e limites de suporte declarados.
4. Registrar resultados diferenciando Linux/Codespaces e Windows/macOS quando não testados.

### Pacote C — Segurança e organização de evidências (L8)

1. Conferir todos os arquivos em `evidencias/` e dados sensíveis potencialmente contidos no histórico Git.
2. Preservar IDs sintéticos e comprovações úteis quando seguros; retirar ou anonimizar o que representar risco.
3. Reorganizar `evidencias/etapa-9/` e referências dependentes, se ainda presentes.
4. Produzir registro sanitizado da revisão; **nunca** incluir credenciais reais no relatório.

## Registro de execução das correções

| Data | ID(s) | Commit/PR | Mudança | Testes/evidência | Status |
|---|---|---|---|---|---|
| — | — | — | Aguardando execução | — | PENDENTE |

## Critérios para reiniciar a auditoria independente

- A tentativa original permanece vinculada ao SHA congelado e seus problemas foram registrados.
- Itens P1 e eventual P0 resolvidos com testes; L2/L6/L7/L8 têm decisão documentada.
- Nova tentativa independente usa um **novo SHA registrado**, e nunca altera silenciosamente o commit da primeira tentativa.
- Critério de aprovação integral: infraestrutura provisionada do zero, CDC e schemas verificados, Flink e alerta de fraude **observados**, teste negativo, evidências sanitizadas, billing e teardown confirmados. Um teste unitário local não substitui essa evidência.

## Próxima ação de Git (a executar pelo responsável no repositório)

> **Não** alterar `chore/project-finalization` enquanto o outro avaliador a examina.

```powershell
git fetch origin
git switch chore/project-finalization
git status -sb
# Exigir diretório limpo e verificar SHA antes de criar a branch.
git log -1 --oneline
git switch -c fix/reproduction-readiness
```

Copiar este arquivo para `docs/audits/reproduction-readiness-backlog.md`, adicioná-lo, fazer commit e publicar a nova branch. Confirmar a ausência de branch preexistente antes de usar `switch -c`. Não criar PR nem fazer merge ainda.
