# Potencial ADR: Mood board como uma única "vibe" (1 prompt → grid de 4) com teto de 8 imagens selecionadas

**Módulo**: MOOD
**Categoria**: Arquitetura
**Prioridade**: Must Document (Score: 125/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: sim — ver "Notas Adicionais": confirmar se o escopo formal do ADR deve cobrir só o que o backend impõe (1 prompt de saída + teto de 8 na seleção) ou também o "grid de 4", que hoje é apenas uma instrução textual (`ui_hint`) para o usuário gerar manualmente na UI da Higgsfield — o Studio não gera nem valida esse grid.
**Data de identificação**: 2026-08-25

## Contexto

A Etapa 2 do curso "O Orquestrador" (aula 009) define o mood board como **uma vibe só**: um
prompt único de ambiente/luz/cor — sem produto, sem pessoas, sem texto — que o usuário gera
como um grid de 4 imagens na UI da Higgsfield, escolhendo depois até 8 imagens do mesmo mood
para compor a paleta e a documentação da campanha. O módulo `MOOD` (`studio/mood/service.py`)
foi construído para reproduzir exatamente essa regra, e não um mood board livre (múltiplos
prompts, categorias por tema, geração ilimitada de candidatas selecionáveis).

Esta não é uma decisão implícita: o próprio `CLAUDE.md` do repositório cita esta correção
como o **exemplo canônico** dos "Gates de fidelidade ao roteiro do curso (IRREVOGÁVEIS)":
"a etapa 2 (mood board) foi corrigida de '6 tipos de prompt' para '1 prompt de vibe × grid de
4', porque é isso que a aula 009 ensina". O histórico git confirma essa origem: o módulo
nasceu no commit inicial de scaffold (`chore: scaffold inicial do Orquestrador Studio (etapas
1 e 2)`, 2026-08-25 02:31) já com a forma atual, e foi explicitamente reforçado no commit
seguinte, `feat: etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e Compozy`
(02:39) — cujo próprio texto de commit nomeia o realinhamento à aula 009 — e depois protegido
por um terceiro commit de correção, `fix: mood valida limite antes de apagar seleção e
bloqueia geração concorrente; docs de brownfield` (02:44), que endureceu a ordem de validação
do teto de 8 imagens em `select()` (antes, o diretório `mood/selected/` era apagado *antes* de
validar o limite; a correção move a checagem de `len(chosen) > 8` para antes de qualquer
efeito colateral em disco). Em outras palavras: em menos de 15 minutos de histórico, a mesma
regra de negócio foi codificada, explicitamente realinhada ao roteiro do curso e depois
endurecida contra perda de dados — um sinal forte de que é uma decisão deliberada e revisada,
não um acidente de implementação.

## Decisão

O `MOOD` implementa a Etapa 2 estritamente como:

1. **Um único prompt de "vibe"** por chamada de `suggest_prompts` — nunca uma lista de prompts
   temáticos/por categoria. A variação (`variation`, 0–3) troca apenas o tratamento estilístico
   de texto (`_STYLE_VARIANTS`), nunca o conteúdo semântico (produto/vibe/hints), e é aplicada
   com módulo circular, então não há um número "certo" de variações a esgotar — o usuário pode
   regenerar indefinidamente sem nunca obter um segundo prompt simultâneo.
2. **Instrução de geração em grid de 4** — comunicada via `ui_hint` textual devolvido ao
   frontend ("gere um grid de 4"), a ser executada manualmente pelo usuário na UI web da
   Higgsfield (caminho "ilimitado no plano"); o caminho pago via CLI (`start_generate`) também
   gera imagens por prompt, mas o número de imagens do grid em si é responsabilidade da
   ferramenta externa, não um parâmetro validado pelo Studio.
3. **Teto rígido de 8 imagens selecionadas** — `select(pid, ids, note)` rejeita com
   `ValueError` ("Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009).")
   qualquer seleção com `len(set(ids)) > 8`, validado antes de qualquer escrita em disco
   (após a correção do commit `fix:` citado acima).

Esse modelo é deliberadamente mais restrito do que um mood board livre/ilimitado ou baseado em
múltiplos prompts por categoria (ex.: um prompt para "cor", outro para "textura", outro para
"iluminação" — um padrão comum em ferramentas de moodboarding), que foi explicitamente
descartado como desvio do roteiro do curso.

## Alternativas Consideradas

- **Múltiplos prompts / categorias de vibe** (ex.: "6 tipos de prompt"): citada literalmente
  no `CLAUDE.md` como a alternativa que foi implementada primeiro e depois revertida por não
  corresponder ao que a aula 009 ensina. Não há mais rastro dela no código atual (o histórico
  git deste repositório começa já no commit de correção), mas o `CLAUDE.md` preserva a memória
  da decisão como exemplo do gate de fidelidade.
- **Seleção sem teto / configurável**: tecnicamente trivial de implementar (bastaria remover a
  condição em `service.py:240-241`), mas rejeitada porque descaracterizaria o conceito de
  "vibe única" da aula — um mood board com dezenas de imagens deixaria de comunicar uma
  direção de arte coesa.
- **Grid de tamanho diferente de 4** (ex.: grid de 6, 9): não há evidência de que isso tenha
  sido implementado ou testado; o número 4 é citado apenas em texto (`ui_hint`) e não é
  parametrizável pelo usuário na API atual.

## Consequências

### Positivas
- Reforça a fidelidade metodológica do produto ao curso, que é o valor central do projeto
  (ver gate irrevogável em `CLAUDE.md`), reduzindo o risco de o Studio "inventar" um método de
  moodboarding próprio e divergir silenciosamente da aula.
- Simplifica a superfície de `suggest_prompts`: sempre retorna exatamente um item em
  `prompts[]`, o que simplifica o contrato de API e a UI (não precisa lidar com N prompts
  paralelos, seleção por categoria, etc.).
- O teto de 8 mantém `mood/selected/`, `palette.json` e `mood.md` pequenos e coerentes com uma
  única direção de arte, o que é relevante porque esses artefatos alimentam (ou alimentarão) a
  Etapa 3 (imagem base), ainda não implementada.
- É protegido por teste automatizado explícito (`test_mood_prompt_is_single_vibe_without_product`,
  que falha com a mensagem "aula 009: um prompt de vibe, gerado em grid de 4" caso a
  invariante seja quebrada) — a regra tem um mecanismo de defesa contra regressão silenciosa.

### Negativas / Trade-offs
- É uma limitação deliberada de produto: um usuário que quisesse explorar múltiplas direções
  de vibe simultaneamente para a mesma campanha precisa rodar o fluxo da Etapa 2 mais de uma
  vez (ou fora do Studio), já que o módulo não guarda "vibes" concorrentes por projeto.
- O número "8" (e o "4" do grid, citado apenas em texto) é um literal inline em
  `service.py:240` (`if len(chosen) > 8:`), sem constante nomeada (`MAX_MOOD_IMAGES`) — o
  relatório de análise de componente já sinaliza isso como fragilidade de manutenibilidade
  (risco Baixo). Qualquer alteração futura de fidelidade ao curso (ex.: se uma aula revisada
  mudar o número) exige achar e mudar esse literal, sem um único ponto de configuração.
- O teto de 8 é validado **somente no backend**: o frontend (`studio/web/app.js`) não impede o
  usuário de marcar mais de 8 candidatas antes de chamar `POST /mood/select` — o único
  feedback é o erro HTTP 422 da API. Isso é uma lacuna de UX (não de arquitetura), mas decorre
  diretamente desta decisão de negócio.
- O "grid de 4" não é verificado nem contado pelo Studio — é confiança no usuário seguir a
  instrução (`ui_hint`) na UI externa da Higgsfield. Se o usuário gerar 8 ou 2 imagens em vez
  de 4, nada no sistema detecta ou impede isso; apenas o teto de seleção final (8) é
  tecnicamente imposto.

## Evidências no Código

### Arquivos-chave
- `studio/mood/service.py` (linhas 68-91) — `suggest_prompts`: monta e retorna sempre
  `"prompts": [{"label": "Vibe da campanha", "text": text}]` (lista de um item), com
  `ui_hint` instruindo "gere um grid de 4" na UI da Higgsfield.
- `studio/mood/service.py` (linhas 60-65) — `_STYLE_VARIANTS`: as 4 variações de estilização
  cíclicas que preservam a vibe/conteúdo semântico do prompt.
- `studio/mood/service.py` (linhas 236-262) — `select`: valida `len(chosen) > 8` antes de
  qualquer escrita em disco (ordem corrigida pelo commit `fix:` mencionado no Contexto).
- `tests/test_mood_service.py` (linhas 16-23) — `test_mood_prompt_is_single_vibe_without_product`:
  assevera `len(r["prompts"]) == 1` e a presença das negações "no product/people/text".
- `tests/test_mood_service.py` (linhas 26-31) — `test_mood_prompt_variations_change_only_style`:
  assevera que só o trecho após "Wide establishing" muda entre variações.
- `tests/test_mood_service.py` (linhas 69-80) — `test_select_writes_palette_and_md_and_caps_at_eight`:
  assevera `ValueError` ao tentar selecionar 9 ids.
- `CLAUDE.md` (linhas 7-36) — gate de fidelidade ao roteiro do curso, citando literalmente
  esta correção ("6 tipos de prompt" → "1 prompt de vibe × grid de 4") como exemplo do gate.
- `docs/domains/mood/hld.md` (linhas 9-14, 35-36) — HLD do domínio, que registra a mesma regra
  como "Objetivo técnico" e como "Padrão adotado" ("Regra de negócio do curso codificada: 1
  prompt, variações só de estilo, teto de 8 imagens no mood").

### Trecho de código
```python
# studio/mood/service.py:68-91
def suggest_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0) -> dict:
    """Aula 009: o mood board é UMA vibe. Um único prompt de ambiente/luz/cor — sem produto,
    sem pessoas, sem texto — gerado em grid de 4 na UI. `variation` troca só a estilização
    ...
    """
    ...
    return {"model": model, "ui_hint": ui_hint, "aspect_ratio": "16:9", "variation": variation,
            "prompts": [{"label": "Vibe da campanha", "text": text}]}

# studio/mood/service.py:236-241
def select(pid: str, ids: list[str], note: str = "") -> dict:
    root = project_dir(pid)
    cands = load(pid)
    chosen = set(ids)
    if len(chosen) > 8:
        raise ValueError("Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009).")
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:31:34 (`chore: scaffold inicial do Orquestrador Studio
  (etapas 1 e 2)`) — a regra já nasce nesta forma no scaffold do projeto.
- Modificado: 3 commits ao todo tocam `studio/mood/service.py` (repositório muito recente,
  todo o histórico é do mesmo dia).
- Reforçado em: 2026-08-25 02:39:46 (`feat: etapa 2 alinhada à aula 009, testes, CI, gitflow,
  skills de projeto e Compozy`) — commit que nomeia explicitamente o realinhamento à aula 009.
- Última mudança: 2026-08-25 02:44:56 (`fix: mood valida limite antes de apagar seleção e
  bloqueia geração concorrente; docs de brownfield`) — endurece a ordem de validação do teto
  de 8 (valida antes de apagar `mood/selected/`), protegendo a regra contra um efeito colateral
  destrutivo em tentativas de seleção inválidas.
- Temas recorrentes nas mensagens de commit: "aula 009", "alinhada", "valida limite" — todos
  apontando para uma decisão de fidelidade ao curso, revisada e endurecida ativamente, não um
  detalhe incidental de implementação.

## ADRs Relacionados / Potenciais

- **HIGGSFIELD** (módulo irmão, analisado em paralelo): a decisão de que o MOOD só interage
  com a Higgsfield via CLI oficial (`--json`, nunca a API HTTP direta, nunca automação de UI)
  é uma decisão do módulo `HIGGSFIELD`, referenciada aqui apenas porque `start_generate` e
  `import_history` dependem dela — não duplicada neste arquivo.
- **STUDIO** (decisões transversais, analisadas em paralelo): persistência em arquivos sob
  `projects/<id>/`, jobs assíncronos em `threading.Thread` (não fila externa), arquitetura
  monolítica e o gate geral de fidelidade ao curso são decisões cross-cutting já cobertas pelo
  módulo `STUDIO` — este ADR pressupõe-nas e não as repete.
- Potencial ADR (não criado nesta análise, descartado por não atingir o score mínimo isolado):
  "caminho duplo de geração — UI manual gratuita (preferencial) vs. CLI paga com confirmação
  de custo" — um eixo de decisão relacionado mas distinto (é sobre *como* a imagem é gerada,
  não sobre *o formato* do mood board). Fica registrado aqui como nota para o caso de o
  usuário decidir formalizar esse ADR mais tarde junto com o HIGGSFIELD.

## Notas Adicionais

- **Precisa de validação do usuário**: o teto de 8 e a menção ao "grid de 4" vivem em
  camadas diferentes de imposição — o teto de 8 é validado por código (`select`, com teste
  cobrindo o caso de erro); o "grid de 4" é apenas uma instrução textual ao usuário
  (`ui_hint`), não verificada nem contada pelo Studio. Ao formalizar o ADR, vale decidir
  explicitamente se o título/escopo do documento deve deixar claro esse assimetria (o que é
  imposto pelo sistema vs. o que é confiado ao usuário seguir na UI externa), para não dar a
  entender que o Studio valida o grid de 4 também.
- O relatório de análise de componente (`docs/agents/component-deep-analyzer/component-analysis-Mood-Service-2026-08-25_02-37-34.md`)
  foi gerado **antes** do commit de correção `fix: mood valida limite antes de apagar seleção
  e bloqueia geração concorrente` (02:44:56) — os dois riscos de severidade "Alto" que esse
  relatório descreve para `select()` (exclusão de `mood/selected/` antes da validação do teto)
  e para `start_generate()` (ausência de lock) **já foram corrigidos** no código atual, como
  confirmado por leitura direta de `studio/mood/service.py` nesta análise. Isso é relevante
  para quem for gerar o ADR formal: o texto do relatório de componente está parcialmente
  desatualizado nesses dois pontos específicos (o resto do relatório permanece válido).
- Não modificar `CLAUDE.md`, `service.py` ou qualquer outro arquivo do projeto foi respeitado
  nesta análise — este arquivo é somente um registro de potencial ADR.
