# ADR-004: Fidelidade ao Roteiro do Curso como Restrição Arquitetural

**Status:** Aceito
**Data:** 2026-08-25

## Contexto e Problema

O Orquestrador Studio não é uma ferramenta genérica de geração de vídeo com IA: ele é
descrito no próprio `CLAUDE.md` (linha 9) como "o método do curso, executável". Cada etapa
cadastrada em `studio/steps.py` aponta, via campo `aula`, para uma aula específica do curso
"O Orquestrador — Iniciante" (ex.: `"009"`, `"010"`...), e a implementação de cada etapa
precisa reproduzir o que o instrutor ensina naquela aula — entradas, saídas, ordem e regras
de qualidade repetidas. Isso levanta um problema arquitetural recorrente: como decidir, de
forma consistente, o que entra em cada etapa do pipeline e o que fica de fora, evitando que
critérios de engenharia (o que é "tecnicamente melhor") substituam silenciosamente o roteiro
pedagógico que dá identidade ao produto.

Essa restrição já não é apenas declarativa. O commit `2b5fd95` ("etapa 2 alinhada à aula 009,
testes, CI, gitflow, skills de projeto e Compozy", 2026-08-25 02:39:46) introduziu o
`CLAUDE.md` com os gates de fidelidade e, no mesmo lote de mudanças, corrigiu
`studio/mood/service.py::suggest_prompts` de um modelo de "6 tipos de prompt" para "1 prompt
de vibe × grid de 4 variações de estilização" — porque é isso que a aula 009 ensina. A
restrição já foi usada, no histórico real do projeto, para reverter uma implementação que
tinha se afastado do roteiro.

O gate "trocar ferramenta não é desvio; trocar processo é" também é o racional documentado
por trás de decisões técnicas específicas de outros módulos deste domínio — por exemplo, o
uso de `HIGGSFIELD` como bridge de CLI em vez de automação da UI da Higgsfield, e o uso de
Playwright para Pinterest em vez de uma API oficial inexistente. Esta restrição de processo
funciona como decisão "guarda-chuva" que justifica e limita várias outras decisões técnicas
do projeto.

## Decision Drivers

- Preservar a proposta de valor central do produto ("o método do curso, executável"), que
  depende de cada etapa reproduzir fielmente a aula correspondente.
- Ter um critério objetivo e verificável para aceitar ou rejeitar mudanças de escopo em
  qualquer etapa, reduzindo debate subjetivo sobre "o que deveria fazer parte do produto".
- Garantir rastreabilidade entre cada decisão técnica de uma etapa e a aula que a origina,
  facilitando auditar se a ferramenta ainda reflete o método ensinado.
- Permitir evolução técnica legítima (troca de ferramenta/plataforma) sem abrir espaço para
  desvio de processo não autorizado.
- Evidência prática de que a restrição previne desvio real: o próprio histórico do
  repositório registra uma correção de escopo motivada por ela.

## Considered Options

1. **Fidelidade estrita ao roteiro do curso, com desvios via aprovação e ADR explícitos**
   (escolhida) — cada etapa reproduz exatamente o que a aula ensina; melhorias fora do
   roteiro podem ser sugeridas, mas só entram no código após aprovação explícita do usuário,
   marcadas como `[extensão]`.
2. **Ferramenta genérica de geração de vídeo com IA, guiada por critérios de engenharia** —
   as etapas seriam desenhadas pelo que é tecnicamente mais fácil, flexível ou robusto,
   usando o curso apenas como inspiração livre, sem obrigação de fidelidade aula a aula.

## Decision Outcome

Chosen option: "Fidelidade estrita ao roteiro do curso, com desvios via aprovação e ADR
explícitos", porque o produto se define pela promessa de ser o método do curso executável, e
não uma ferramenta de propósito geral. A alternativa de tratar o curso como inspiração livre
é descartada explicitamente pelo próprio `CLAUDE.md` ("Ele não é um lugar para inventar um
método novo"). Toda etapa do pipeline (`studio/steps.py`) deve reproduzir fielmente o que a
aula correspondente ensina; nada além disso entra na etapa sem aprovação explícita do
usuário. Trocar a ferramenta/plataforma usada em uma aula é aceitável desde que a etapa
produza o mesmo artefato que a aula produz; trocar o processo em si não é. Toda decisão de
desvio do roteiro vira um ADR em `docs/adrs/` e uma nota na etapa — nunca um desvio
silencioso. Antes de codar uma etapa nova, é preciso escrever em uma frase o que a aula faz e
o que a etapa vai produzir, checando com o usuário em caso de ambiguidade.

Exemplo concreto já aplicado: a etapa 2 (mood board) foi corrigida de um modelo de "6 tipos
de prompt" para "1 prompt de vibe × grid de 4 variações de estilização", porque é isso que a
aula 009 ensina — hoje refletido no comentário de `suggest_prompts` em
`studio/mood/service.py`. Esse é o padrão de referência para qualquer decisão futura de
escopo: primeiro checar o que a aula ensina; extensões (como character sheet, color match ou
hook nos 3 s, citadas como exemplos no `CLAUDE.md`) permanecem apenas sugeridas até aprovação
explícita, e só então entram marcadas como `[extensão]`.

Decisão registrada na adoção (2026-08-25): a aprovação é do dono do produto, de forma ad-hoc e explícita (mensagem, comentário no PR ou no card do Trello). Extensão aprovada entra marcada `[extensão]` e, quando muda processo ou artefato de uma etapa, ganha ADR antes do merge — o registro é consequência da aprovação, não pré-requisito dela.

## Pros and Cons of the Options

### Opção 1: Fidelidade estrita ao roteiro do curso (escolhida)

- Boa, porque fornece critério objetivo e verificável para aceitar ou rejeitar mudanças de
  escopo em qualquer etapa.
- Boa, porque mantém rastreabilidade entre decisão técnica e fonte pedagógica (aula),
  facilitando auditoria futura.
- Boa, porque já demonstrou funcionar na prática, corrigindo um desvio real no histórico do
  projeto.
- Ruim, porque limita a velocidade de inovação técnica: melhorias óbvias de engenharia não
  podem ser implementadas sem parar e pedir aprovação explícita.

### Opção 2: Ferramenta genérica guiada por critérios de engenharia

- Boa, porque permitiria maior liberdade técnica e velocidade de iteração sem depender de
  aprovação externa a cada melhoria identificada.
- Ruim, porque descaracterizaria a proposta de valor central do produto, que é ser
  literalmente o método do curso executável.
- Ruim, porque removeria o critério objetivo hoje usado para decidir escopo, reabrindo debate
  subjetivo em cada etapa.
- Ruim, porque não há evidência de que essa alternativa tenha sido formalmente avaliada por
  escrito antes da decisão atual.

## Consequences

A restrição acopla o roadmap do produto ao roadmap do curso: mudanças no curso (novas aulas,
aulas revisadas) obrigam revisão do produto para manter a fidelidade. Ela também introduz um
processo de decisão adicional — registro obrigatório em ADR para qualquer desvio — que é
overhead mesmo quando o desvio é pequeno e tecnicamente óbvio, como trocar uma ferramenta por
limitação de termos de uso.

Em contrapartida, toda mudança futura de escopo em qualquer etapa do pipeline passa a ter um
teste objetivo: comparar com o que a aula correspondente ensina. Isso reduz a chance de o
produto derivar silenciosamente para uma ferramenta genérica, mas exige que os planos
aula-a-aula (`docs/plano/plano-automacao-videos.md` e `docs/plano/plano-higgsfield.md`) sejam
mantidos como referência normativa viva, já que são a fonte primária citada pelo `CLAUDE.md`
para o que cada aula ensina.

Decisão registrada na adoção (2026-08-25): caso a caso. O instrutor avisa (aula 005) que insere atualizações no meio das aulas; ao notar divergência, abre-se um card e o fluxo `dd-docs`/`dd-feature` reconcilia `docs/plano/` e a etapa afetada. Não há sincronização automática com a plataforma do curso.

## References

- `CLAUDE.md:7-36`
- `studio/steps.py:7-30`
- `studio/mood/service.py:69-72`
- `docs/adrs/mapping.md:384-412`
- `docs/plano/plano-automacao-videos.md`
