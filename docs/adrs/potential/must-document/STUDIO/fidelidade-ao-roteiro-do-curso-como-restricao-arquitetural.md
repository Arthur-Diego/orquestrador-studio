# Potencial ADR: Fidelidade ao Roteiro do Curso como Restrição Arquitetural

**Módulo**: STUDIO
**Categoria**: Processo
**Prioridade**: Must Document (Score: 140/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: não
**Data de identificação**: 2026-08-25

## Contexto

O Orquestrador Studio não é um produto genérico de geração de vídeo com IA: ele é, literalmente,
"o método do curso, executável" (`CLAUDE.md`, linha 9). Cada etapa cadastrada em
`studio/steps.py` aponta para uma aula específica do curso "O Orquestrador — Iniciante" (campo
`aula`, ex.: `"009"`, `"010"`...), e a implementação de cada etapa deve reproduzir exatamente o
que o instrutor ensina naquela aula — entradas, saídas, ordem e regras de qualidade repetidas.
Isso é formalizado como um conjunto de 5 gates "irrevogáveis" em `CLAUDE.md` (linhas 7-36),
espelhados também na seção "Fidelidade ao curso" de `docs/adrs/mapping.md` (linhas 384-412).

O commit `2b5fd95` ("etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e
Compozy", 2026-08-25 02:39:46) é o mesmo commit que introduziu o `CLAUDE.md` com esses gates e
que, no mesmo lote de mudanças, corrigiu `studio/mood/service.py::suggest_prompts` de um modelo
de "6 tipos de prompt" para "1 prompt de vibe × grid de 4 variações de estilização" — porque é
isso que a aula 009 ensina (comentário explícito no código: "Aula 009: o mood board é UMA vibe.
Um único prompt de ambiente/luz/cor... `variation` troca só a estilização"). Ou seja, a
restrição não é apenas declarativa: ela já foi usada, no próprio histórico do projeto, para
reverter uma implementação que tinha se afastado do roteiro da aula.

O gate 3 do `CLAUDE.md` ("Trocar ferramenta não é desvio; trocar processo é") é o racional
documentado por trás de decisões técnicas específicas deste módulo e de outros — por exemplo, a
escolha de `HIGGSFIELD` como bridge de CLI em vez de automação da UI da Higgsfield, e o uso de
Playwright para Pinterest em vez de uma API oficial (que não existe). Ou seja, esta restrição de
processo é a decisão "guarda-chuva" que justifica e limita várias outras decisões técnicas do
projeto.

## Decisão

Toda etapa do pipeline (`studio/steps.py`) deve reproduzir fielmente o que a aula correspondente
do curso ensina; nada além do que a aula ensina entra na etapa sem aprovação explícita do
usuário. Melhorias fora do roteiro podem ser **sugeridas**, mas não implementadas
silenciosamente — quando aprovadas, são marcadas como `[extensão]` no código e na documentação.
Trocar a ferramenta/plataforma usada em uma aula é aceitável desde que a etapa produza o mesmo
artefato que a aula produz; trocar o processo em si não é. Toda decisão de desvio do roteiro
vira um ADR em `docs/adrs/` e uma nota na etapa — nunca um desvio silencioso. Antes de codar uma
etapa nova, é preciso escrever em uma frase o que a aula faz e o que a etapa vai produzir, e
checar com o usuário em caso de ambiguidade.

## Alternativas Consideradas

Não há evidência direta no código de alternativas descartadas por escrito (não há, por exemplo,
um ADR anterior comparando "seguir o curso à risca" vs. "usar o curso como inspiração livre").
Mas a estrutura do próprio projeto deixa a alternativa implícita: seria possível construir uma
ferramenta de produção de vídeo com IA mais genérica, com etapas desenhadas por critérios de
engenharia (o que é tecnicamente mais fácil/flexível) em vez de por fidelidade pedagógica a um
curso de terceiros. O `CLAUDE.md` descarta essa alternativa explicitamente ("Ele não é um lugar
para inventar um método novo").

## Consequências

### Positivas
- Critério objetivo e verificável para aceitar ou rejeitar mudanças de escopo em qualquer etapa,
  reduzindo debate subjetivo sobre "o que deveria fazer parte do produto".
- Rastreabilidade entre decisão técnica e fonte pedagógica (aula), o que facilita auditar se a
  ferramenta ainda reflete o método ensinado.
- Já demonstrou funcionar na prática: preveniu/corrigiu um desvio real (mood board com 6 tipos de
  prompt em vez de 1 vibe única) no próprio histórico do repositório.

### Negativas / Trade-offs
- Limita a velocidade de inovação técnica: melhorias óbvias de engenharia (ex.: character sheet,
  color match, hook nos 3s — citadas como exemplos no próprio `CLAUDE.md`) não podem ser
  implementadas sem parar e pedir aprovação explícita do usuário, mesmo quando o time técnico as
  considera claramente benéficas.
- Acopla o roadmap do produto ao roadmap do curso: mudanças no curso (novas aulas, aulas
  revisadas) obrigam revisão do produto para manter a fidelidade.
- Introduz um processo de decisão adicional (registro obrigatório em ADR) para qualquer desvio,
  o que é overhead de processo mesmo quando o desvio é pequeno e tecnicamente óbvio (ex.: trocar
  uma ferramenta por limitação de termos de uso).

## Evidências no Código

### Arquivos-chave
- `CLAUDE.md` (linhas 7-36) — os 5 gates de fidelidade, com exemplo real de aplicação (mood
  board corrigido de "6 tipos de prompt" para "1 prompt de vibe × grid de 4")
- `docs/adrs/mapping.md` (linhas 384-412) — seção "Fidelidade ao curso (gates do CLAUDE.md)",
  documentando esta restrição como transversal a todos os módulos de domínio
- `studio/steps.py` (linhas 7-30) — catálogo de 11 etapas, cada uma com campo `aula` referenciando
  a aula do curso que a define
- `studio/mood/service.py` (linhas 1-4, 69-72) — docstring do módulo e comentário em
  `suggest_prompts` citando explicitamente "Aula 009" como fonte de verdade da lógica de prompts

### Trecho de código
```python
# studio/mood/service.py
def suggest_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0) -> dict:
    """Aula 009: o mood board é UMA vibe. Um único prompt de ambiente/luz/cor — sem produto,
    sem pessoas, sem texto — gerado em grid de 4 na UI. `variation` troca só a estilização
    (o que o instrutor faz ao ajustar Stylization e regerar quando o grid 'não pegou a vibe').
    Produto na cena, escala e rótulo pertencem à etapa 3 (imagem base)."""
```

```python
# studio/steps.py
STEPS = [
    {"id": "refs", "n": 1, "title": "Referências", "aula": "009", "status": "ready", ...},
    {"id": "mood", "n": 2, "title": "Mood board", "aula": "009", "status": "ready", ...},
    {"id": "base", "n": 3, "title": "Imagem base", "aula": "009", "status": "soon", ...},
    ...
]
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:39:46 (commit `2b5fd95`), junto com testes, CI, gitflow e o
  próprio `CLAUDE.md` — não existia no scaffold inicial (`b29700a`)
- Modificado: sem alterações posteriores até o commit mais recente (`155a787`) analisado
- Aplicado na prática nesse mesmo commit: correção de `mood/service.py` de "6 tipos de prompt"
  para "1 prompt de vibe × grid de 4", citando a aula 009 como justificativa
- Repositório é recente (todo o histórico está concentrado em 2026-08-25); não há ainda um ciclo
  longo de evolução para observar se a restrição se mantém estável ao longo de meses

## ADRs Relacionados / Potenciais

- Relaciona-se diretamente com "Ponte com o CLI Higgsfield via Subprocess" (também potencial ADR
  do módulo STUDIO nesta análise) — é o exemplo citado no próprio `CLAUDE.md` de "trocar
  ferramenta não é desvio".
- Relaciona-se com "Automação de Navegador via Playwright com Perfil Persistente" (Pinterest) —
  outro caso de "troca de ferramenta legítima" (scraping em vez de API oficial, que não existe).
- É a motivação estrutural por trás do catálogo estático de 11 etapas em `studio/steps.py`.

## Notas Adicionais

Metodologia de pontuação aplicada: por se tratar de uma restrição de processo que define a
própria proposta de valor central do produto ("o método do curso, executável"), foi tratada por
julgamento como infraestrutura crítica ao domínio (nota "Domain-Specific Infrastructure" do
Step 0), com score base 70, mais Escopo+Impacto 25 (afeta todos os módulos e todo trabalho
futuro), Custo de Mudança 25 (reverter equivaleria a redefinir a identidade do produto) e
Conhecimento da Equipe 20 (necessário antes de codar qualquer etapa nova, ainda que não seja
necessário para toda tarefa de manutenção pontual) — total 140/150.

Uma dúvida em aberto não bloqueante: o `CLAUDE.md` cita `docs/plano/plano-automacao-videos.md` e
`docs/plano/plano-higgsfield.md` como fonte normativa aula-a-aula, mas esses arquivos ficaram
fora do escopo deste mapeamento por instrução explícita anterior — uma ADR formal desta decisão
deveria linkar para eles como referência primária.
