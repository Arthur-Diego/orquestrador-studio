### FDD: base-prompt-provenance — deixar visível a junção mood × referência no prompt da base

Task-Id: ADH-OS-20260827-08 · Domínio: studio (etapa base + prompter) · Base: `develop` (pós #56)
Pedido do dono do produto (27/08/2026): "no painel 01 da imagem-base, dentro do prompt gerado,
mostrar qual parte é referência do mood e qual é a outra parte — deixar claro que existe uma junção
do mood com a imagem de referência."

### 0. Fato do domínio (verificado no código)

O prompt da base é escrito pelo bot (Claude) fundindo: a **situação/composição da imagem de
referência** (etapa 1) + a **vibe do mood** (luz, paleta, atmosfera — imagens de `mood/selected`,
`project.vibe`, paleta). O papel do bot (`prompter.ROLES["base"]`) é literalmente "place the product
in EXACTLY the same situation/composition as the reference image, keeping the campaign mood (light,
palette, atmosphere)". O prompt segue um FORMATO fixo: 1 parágrafo + 5 linhas nomeadas
(`Camera:`, `Lighting:`, `Composition:`, `Color grading:`, `Style:` — `prompter.PROMPT_SECTIONS`).

### 1. Mapa de proveniência (determinístico, fiel ao papel do bot)

| Trecho do prompt | Proveniência | Rótulo na UI |
|---|---|---|
| Parágrafo (produto + situação, na atmosfera) | junção | "junção — produto da referência na vibe do mood" |
| `Composition:` | referência | "referência (situação/enquadramento)" |
| `Lighting:` | mood | "mood (luz)" |
| `Color grading:` | mood | "mood (cor/paleta)" |
| `Style:` | mood | "mood (estética/atmosfera)" |
| `Camera:` | técnico | "técnico" |

Isto NÃO depende de o modelo "explicar" nada — mapeia as linhas do formato garantido. Degradação
graciosa: se alguma linha nomeada faltar, mostrar o prompt inteiro normalmente + a legenda geral.

### 2. Backend (`studio/common/prompter.py` + `studio/base/service.py`)

- Novo helper em `prompter.py`: `split_sections(prompt) -> {"paragraph": str, "sections": {"Camera":..,
  "Lighting":.., "Composition":.., "Color grading":.., "Style":..}}` (parser do formato; robusto a
  linha faltando). Reusar `PROMPT_SECTIONS`.
- `base.generate_prompt` (e o histórico salvo em `prompts.json`) passa a incluir `provenance`:
  `{"paragraph": <str>, "parts": [{"label": "Composition", "text": <str>, "from": "reference"},
  {"from":"mood",...}, {"from":"technical",...}]}` derivado do `split_sections` + o mapa da §1.
  Também expor, para a UI, os arquivos de referência e de mood já usados: `ref_file` (já existe) e as
  imagens do mood/board que entraram como referência (o `_ref_mood_paths` já sabe; devolver os
  caminhos relativos para thumbs) + `palette`.
- Sem mudança de comportamento de geração; só enriquece o retorno. `mode=template` também recebe
  `provenance` (o template tem as mesmas 5 linhas).

### 3. Frontend (etapa 3 base — `studio/etapas/base/view.*`)

No painel 01, ao exibir o prompt gerado:
- **Cabeçalho de junção**: uma faixa com dois blocos lado a lado —
  🖼️ **Referência (situação)**: thumb da referência escolhida (etapa 1);
  🎨 **Mood (vibe/luz/cor)**: thumbs do mood aplicado (ou do board escolhido na etapa 3) + a paleta.
  Texto: "O prompt abaixo funde a **situação da referência** com a **vibe do mood**."
- **Prompt anotado**: manter o `<textarea>` copiável com o prompt COMPLETO (não quebrar copiar), e
  ADICIONAR acima/ao lado uma visão anotada (read-only) das 5 linhas com um **chip de proveniência**
  por linha (referência / mood / técnico), cores distintas (usar tokens: `--accent` p/ mood,
  `--info`/`--ink` p/ referência, `--ink-4` p/ técnico). O parágrafo com o rótulo "junção".
- Não remover nada do que já existe (o prompt copiável, "Copiar", editar). É acréscimo de clareza.
- `[extensão]`? É clareza de UI sobre o que a aula já faz (a aula manda "mostrar mood + referência ao
  bot"); marcar a visão anotada como `[extensão]` discreto, já que o protótipo não a desenha.

### 4. Testes

- `tests/test_base_api.py`: `generate_prompt`/`GET base/prompts` (ou o POST) devolve `provenance` com
  as partes rotuladas por `from` (reference/mood/technical) e o parágrafo; robustez a linha faltante.
- prompter: teste de `split_sections` (parágrafo + 5 seções; caso de seção ausente).
- `test_base_view` (fidelidade): a visão anotada e o cabeçalho de junção existem no HTML/JS, sem
  remover o textarea copiável nem os 3 painéis do curso (contrato da wave 4). Ajustar contagem só se
  necessário, justificando.
- Não reduzir baseline.

### 5. Verificação

- `make verify` verde.
- Smoke Playwright: numa campanha com referência (etapa 1) + mood aplicado (etapa 2), gerar o prompt
  da base → aparecem o cabeçalho de junção (thumbs ref + mood + paleta) e as linhas com chips de
  proveniência; o textarea copiável continua com o prompt completo. 0 erro; dark+light. Prints fora
  do git.

### 6. Fora de escopo

- Fazer o bot "rotular" a proveniência (parsing determinístico basta e é honesto).
- Reescrever o formato do prompt.
