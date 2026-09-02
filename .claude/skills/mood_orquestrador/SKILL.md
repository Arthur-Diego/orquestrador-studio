---
name: mood_orquestrador
description: >
  Porta de entrada da cadeia de mood: pergunta qual foto você escolheu (aceita arquivo,
  trecho do nome ou diretório), manda a `mood_visual_dna` extrair o DNA visual dela em JSON
  validado, e entrega esse DNA para a `mood_board_builder` buscar, baixar e montar a prancha
  `_moodboard.jpg`. Gera um board por objetivo — `ambiente`, `campanha`, `produto`,
  `personagem` — aceitando um, vários (`--objetivo a,b`) ou `todos`, e as paradas humanas são
  parametrizáveis (`--gate interativo|auto`), o que permite chamada programática por uma tela.
  Use quando já existirem fotos coletadas e o pedido for "escolhi essa, quero mais dessa vibe"
  ou "monta meu moodboard a partir dessa imagem". Use `mood_vibe_scout` quando ainda não
  houver foto escolhida e a vibe precisar ser descoberta do zero.
---

# Orquestrador do mood (mood_orquestrador) `[extensão]`

Encadeia as três skills da família `mood_` em uma corrida só:

```
  você escolheu uma foto
          ↓
  mood_orquestrador ── pergunta qual é, confirma escopo
          ↓
  mood_visual_dna ──── DNA visual + paleta + consultas por função (JSON validado)
          ↓
  mood_board_builder ─ busca · baixa · cura · monta _moodboard.jpg
```

Antes disso, quando ainda não há foto escolhida, quem roda é a `mood_vibe_scout`
(entrevista → shortlist de vibes → 3 fotos de cada, para você escolher).

`[extensão]`: pesquisa e diagramação de referência. Não gera imagem com IA, não gasta crédito
Higgsfield e não escreve o prompt de vibe da etapa 2 (aula 009).

<HARD-GATE>
**Proibições — não dependem de parâmetro, valem sempre:**
- Nunca gerar imagem com IA nem gastar crédito Higgsfield.
- Nunca publicar, enviar ou subir as imagens para lugar nenhum. Uso local.
- Nunca afirmar autoria, licença ou "livre para uso" de imagem alguma.
- Nunca montar um board com mais de uma foto-semente.

**Paradas — parametrizáveis por `--gate`:**
1. **Qual imagem** (Passo 1) · 2. **Aprovar a leitura** (Passo 4) · 3. **Aprovar a curadoria**
   (dentro da `mood_board_builder`).

`--gate interativo` (default): as três acontecem.
`--gate auto`: nenhuma acontece — cada uma vira uma decisão determinística registrada em
arquivo e reportada na entrega. Em `auto` a foto e o objetivo têm de vir por parâmetro; sem
eles, pare e diga o que falta (é a única interrupção permitida em `auto`).
</HARD-GATE>

## Invocação

```
/mood_orquestrador [ARQUIVO|TRECHO|DIRETÓRIO] [--objetivo LISTA|todos] [--gate interativo|auto]
                   [--n N] [--board N] [--saida DIR] [--fundo escuro|claro] [--params ARQ.json]
```

| Parâmetro | Valores aceitos | Default | O que faz |
|---|---|---|---|
| posicional ou `--foto` | caminho de arquivo, trecho de nome ou diretório | pergunta (Passo 1) | a foto-semente |
| `--objetivo` | `ambiente` · `campanha` · `produto` · `personagem` · lista separada por vírgula · `todos` | pergunta (Passo 1) | quais boards gerar — **um por objetivo** |
| `--gate` | `interativo` · `auto` | `interativo` | se as três paradas humanas acontecem |
| `--board` | inteiro ≥ 4 | `8` | referências por prancha |
| `--n` | inteiro ≥ 1 | `3` | candidatas baixadas por consulta |
| `--saida` | diretório | `processo_manual/moodboard/` | **raiz**; cada objetivo ganha uma subpasta própria |
| `--fundo` | `escuro` · `claro` | `escuro` | tema da prancha |
| `--params` | caminho de um JSON | — | mesmas chaves acima, para chamada programática |

Valor de `--objetivo` fora da lista → pare e diga quais são os aceitos; não adivinhe o mais
parecido.

### A conta antes de baixar

```
consultas por board = --board - 1        (a semente já ocupa uma vaga)
downloads           = objetivos × consultas × --n
```

`--objetivo todos --board 8 --n 3` = 4 × 7 × 3 = **84 downloads**. Diga o número **antes** de
começar, nos dois modos de gate — em `interativo` como aviso, em `auto` como primeira linha do
relatório.

### Saída por objetivo

Um objetivo, um board, uma pasta. O objetivo vai no **sufixo**:

```
<saida>/board-<slug-da-vibe>-<objetivo>/
```

Cada pasta tem o `dna.json` **dela**: o objetivo muda as consultas por função, então um DNA por
objetivo — nunca reaproveite o `dna.json` de um objetivo em outro.

### Chamada programática (`--params`)

Para uma tela chamar o fluxo sem montar string de flags:

```json
{
  "foto": "processo_manual/moodboard/fotos_escolhidas/23-anime-city-night-3.jpg",
  "objetivo": ["ambiente", "campanha"],
  "gate": "auto",
  "board": 8,
  "n": 3,
  "saida": "processo_manual/moodboard",
  "fundo": "escuro"
}
```

Chave ausente cai no default da tabela. Flag na linha de comando ganha da chave no JSON.

Ao final de qualquer corrida, grave `<saida>/_run.json` — é o que a tela lê de volta:

```json
{
  "semente": "…/23-anime-city-night-3.jpg",
  "gate": "auto",
  "boards": [
    {"objetivo": "ambiente", "pasta": "…/board-anime-city-night-ambiente",
     "prancha": "…/_moodboard.jpg", "imagens": 8, "refeitas": [], "trocas": []}
  ],
  "downloads": 21
}
```

## Os quatro objetivos

O objetivo não é rótulo: é o que decide **quais funções ocupam as 7 vagas** e como as consultas
são escritas. Mesma semente, objetivos diferentes, boards diferentes.

| `--objetivo` | A pergunta que o board responde | Funções que ele privilegia |
|---|---|---|
| `ambiente` | onde a história acontece? | hero · atmosfera · textura · objeto/moldura · ambiente · tipografia · tradução 3D |
| `campanha` | o que a campanha afirma? | key visual · assinatura de luz · atitude/styling · cor · tipografia · textura · tradução de modalidade |
| `produto` | como o objeto existe nesse mundo? | hero de produto · still life · atmosfera · material · render/packshot · produto em contexto · embalagem |
| `personagem` | quem vive nesse mundo? | corpo inteiro · retrato · figurino · pose · luz de personagem · prop · expressão |

Quando a semente não contém o assunto do objetivo — uma paisagem pedida como `produto`, por
exemplo — o board inteiro é **extrapolação de cor, luz e material**, não leitura. Isso é
legítimo, mas diga na entrega: é a diferença entre o que a foto mostra e o que você deduziu.

## Sequência

Os passos marcados **[I]** são interativos em `--gate interativo` e viram **[A]** — decisão
determinística registrada em arquivo — em `--gate auto`. Cada passo diz o que fazer nos dois.

1. **[I/A] Descobrir qual foto foi escolhida e o escopo da corrida.**

   **Em `--gate auto`:** `--foto` tem de apontar um arquivo existente e `--objetivo` tem de
   estar preenchido. Faltando qualquer um dos dois, pare e diga exatamente o que falta. Nada de
   `AskUserQuestion`, nada de escolher a foto mais recente por conta própria.

   **Em `--gate interativo`,** monte as candidatas assim:
   - Argumento é caminho de arquivo → é essa, confirme em uma linha e siga.
   - Argumento é trecho de nome → `ls` filtrado na pasta padrão; um resultado, siga; vários,
     pergunte entre eles.
   - Argumento é diretório, ou não veio argumento → liste as imagens de
     `processo_manual/moodboard/fotos_vibe/` (ou do diretório dado) ordenadas pela mais
     recente.

   Então **pergunte com `AskUserQuestion`**: *"Qual imagem você escolheu?"*, com até 4
   candidatas como opções — nome do arquivo + a vibe dele lido do `_indice.json`, quando
   existir. O campo "Other" da pergunta aceita qualquer outro nome digitado, então não é
   preciso listar tudo. Se houver muitas candidatas, monte antes uma folha de contato
   numerada para a pessoa olhar:
   ```bash
   .venv/bin/python .claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py \
     --plano <plano do lote> --so-folhas
   ```
   **Uma foto só.** A pasta de escolhidas é a peneira da pessoa, não o conteúdo do board: o
   board nasce de **uma** semente e é montado em volta dela. Se ela apontar várias, pergunte
   qual é a referência desta rodada — não junte todas num board.

   Na mesma chamada de `AskUserQuestion`, pergunte o que ainda não sabe (máx. 4 no total):
   **objetivo(s)** do board, quantas referências na prancha e se o fundo é escuro ou claro.
   Na pergunta de objetivo, ofereça as quatro opções e deixe claro que dá para marcar mais de
   uma (`multiSelect`) — cada marcada vira um board separado.

2. **[S] Confirmar o alvo.** Leia a imagem escolhida com o `Read` — você precisa **ver** a
   foto, não só o nome. Se o arquivo não abrir, pare e diga; não analise pelo nome. Isso vale
   nos dois modos de gate: `auto` não autoriza analisar imagem que você não abriu.

3. **[S] Extrair o DNA — um por objetivo.** Para cada objetivo pedido, invoque
   `mood_visual_dna` passando a imagem **e aquele objetivo**, dizendo como ele reordena as
   funções do board. Exija explicitamente a **saída JSON** dela (o padrão dela é Markdown),
   grave em `<saida>/board-<slug>-<objetivo>/dna.json` e valide:
   ```bash
   .venv/bin/python .claude/skills/mood_visual_dna/scripts/validate_visual_dna.py <arquivo>
   ```
   Inválido → conserte antes de seguir. Com vários objetivos, dispare as extrações **em
   paralelo** (uma por subagente): elas não dependem uma da outra.

4. **[I/A] A leitura.**

   **`interativo`:** mostre e pare. Em no máximo 10 linhas por objetivo: vibe principal e
   confiança, paleta (dizendo que é **aproximada**) e as consultas por função. Pergunte se a
   leitura bate. Se a pessoa corrigir a vibe, ajuste o `dna.json` e mostre de novo — a
   correção dela vale mais que a sua leitura.

   **`auto`:** não pergunte. Grave a mesma leitura em
   `<saida>/board-<slug>-<objetivo>/leitura.md` e siga, registrando
   `[auto] leitura aceita sem revisão humana`. A leitura fica no disco justamente para ser
   auditada depois.

5. **[S] Buscar, baixar e montar.** Para cada objetivo, invoque `mood_board_builder` com
   `--dna <pasta do objetivo>/dna.json`, `--gate` **igual ao seu** e os demais parâmetros.
   Rode os objetivos **em série** — o coletor vai à mesma fonte, e paralelizar download só
   aumenta a chance de vir vazio.

6. **[S] Entregar.** Grave o `_run.json` e reporte: caminho de cada prancha, quantas imagens
   entraram, o que foi refeito, o que foi trocado e por quê. Em 2–3 frases por board, o que
   aquela direção afirma e **onde ela ficou frágil** — função que veio fraca, paleta que não
   fechou, imagem que entrou como contraste deliberado. Com vários objetivos, feche dizendo
   qual board está mais coerente e para que serve cada um.

   Em `--gate auto`, a entrega é o único momento de revisão que a pessoa vai ter: liste
   explicitamente toda decisão que teria sido uma pergunta.

## Regras

- **Em `interativo`, sempre pergunte qual é a imagem.** Mesmo com um só candidato óbvio: é a
  foto que a pessoa escolheu que define tudo o que vem depois, e errar aqui joga fora a corrida
  inteira. Em `auto`, a foto vem por parâmetro ou a corrida não começa — nunca escolha por ela.
- **`auto` desliga a pergunta, não a regra.** Cada parada pulada continua sendo uma decisão que
  precisa do mesmo critério de sempre, registrada em arquivo e listada na entrega. Se em `auto`
  você encontrar algo que só um humano resolve — a foto não abre, dois objetivos produzem o
  mesmo board, o DNA não valida depois de conserto — pare e diga; não invente saída.
- **Um objetivo, um board, uma pasta.** Nunca junte dois objetivos na mesma prancha e nunca
  reaproveite o `dna.json` de um objetivo em outro: é o objetivo que decide as consultas.
- **Não pule a `mood_visual_dna`.** A tentação é olhar a foto e escrever as queries direto.
  O valor dela está em separar `Observado` de `Inferido` e em cobrir as funções do board — não
  improvise isso.
- Se a pessoa ainda **não escolheu** foto nenhuma, esta não é a skill: mande para a
  `mood_vibe_scout` e volte quando houver escolha.
- Não afirme autoria, licença ou "livre para uso" de imagem alguma.
- Pastas de saída são material local. Confirme o `.gitignore` antes de qualquer `git add`.

## A família `mood_`

| Skill | Momento | Entrega |
|---|---|---|
| `mood_vibe_scout` | não sei qual vibe quero | entrevista → 3 fotos × N vibes → você escolhe |
| `mood_visual_dna` | já escolhi uma foto | DNA visual, paleta, consultas por função |
| `mood_board_builder` | tenho o DNA | busca, baixa, cura e monta a prancha |
| `mood_orquestrador` | quero tudo de uma vez | encadeia as três acima |
