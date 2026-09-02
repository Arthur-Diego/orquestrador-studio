---
name: mood_board_builder
description: >
  Monta um moodboard em volta de UMA foto-semente: recebe o DNA visual dela (JSON da
  `mood_visual_dna`), escolhe as consultas por função (hero, atmosfera, textura, styling ou
  objeto, ambiente, tipografia, tradução 2D/3D), busca no Pinterest, cura e monta a prancha
  `_moodboard.jpg` com hero, grade e faixa de paleta. Board padrão de **8**: a foto-semente
  como hero + 7 de busca, o que dá 7 consultas × 3 candidatas = 21 downloads — o tamanho do
  board manda no número de consultas, nunca o contrário. Use quando já houver uma foto
  escolhida e o pedido for "pegar mais imagens dessa vibe" ou "montar o moodboard". A parada de
  curadoria é parametrizável (`--gate interativo|auto`), o que permite chamada programática por
  uma tela. Não use para descobrir a vibe do zero (é `mood_vibe_scout`) nem para analisar a
  imagem (é `mood_visual_dna`).
---

# Expandir e montar o moodboard (mood_board_builder) `[extensão]`

Terceiro elo da cadeia: **descobrir** (`mood_vibe_scout`) → **ler**
(`mood_visual_dna`) → **expandir e montar** (esta). Entra com um DNA visual, sai com uma
prancha diagramada e as imagens indexadas.

`[extensão]`: pesquisa e diagramação de referência. Não gera imagem com IA, não escreve o
prompt de vibe da etapa 2 (aula 009) e não substitui o mood board do curso.

<HARD-GATE>
**Proibições — não dependem de parâmetro, valem sempre:** gerar imagem com IA, gastar crédito
Higgsfield, publicar ou enviar as imagens para qualquer lugar, afirmar autoria ou licença, e
montar board com mais de uma foto-semente. São referências de terceiros baixadas do Pinterest:
uso local, sem commit.

**Parada — parametrizável por `--gate`:** aprovar a curadoria (Passo 5) — quais entram no board
e qual é a hero — antes de montar a prancha.
- `--gate interativo` (default): mostre a lista final e pare para aprovação.
- `--gate auto`: não pergunte. Aplique o mesmo teste de coerência, grave a lista escolhida
  **e os descartes com o motivo** em `<saida>/curadoria.md`, e siga.

O resto é regra determinística nos dois modos, reportado em uma linha `[decisão] …`.
</HARD-GATE>

## Invocação

```
/mood_board_builder [--dna ARQ.json] [--foto CAMINHO] [--objetivo NOME] [--gate interativo|auto]
                       [--n N] [--board N] [--saida DIR] [--fundo escuro|claro]
```

- `--dna`: JSON produzido pela `mood_visual_dna`. **É o caminho normal** — traz paleta,
  vibe e consultas por função já prontas.
- `--objetivo`: `ambiente` · `campanha` · `produto` · `personagem`. **Um só** — esta skill monta
  um board por vez; quem faz vários objetivos numa corrida é a `mood_orquestrador`. Serve para
  ordenar as vagas (Passo 2b) e para nomear a pasta de saída.
- `--gate`: `interativo` (default) para na curadoria; `auto` decide sozinho e registra em
  `<saida>/curadoria.md`. Ver o HARD-GATE acima.

## A conta — leia antes de baixar

O tamanho do board manda no número de consultas, **nunca o contrário**:

```
consultas = --board - 1        (a foto-semente já ocupa um lugar no board)
downloads = consultas × --n
```

Board de 8 → **7 consultas × 3 candidatas = 21 downloads**, dos quais 7 entram na prancha.

Rodar as 10 funções do catálogo num board de 8 baixa o dobro para descartar o dobro. O
catálogo de funções em `references/board.md` é uma **lista de prioridade**, não uma lista de
obrigações: você corta nela na altura de `--board - 1`.

## Sequência

1. **[I] Garantir o DNA.** Sem `--dna`, produza um invocando a skill `mood_visual_dna`.
   Exija dela a **saída JSON** (o padrão dela é Markdown) e valide antes de seguir:
   ```bash
   .venv/bin/python .claude/skills/mood_visual_dna/scripts/validate_visual_dna.py dna.json
   ```
   JSON inválido → conserte antes do Passo 2; não adivinhe campo faltando.

2. **[C] Escolher as consultas e montar o plano.** O DNA traz cerca de 12 consultas; você vai
   usar **`--board - 1`** delas. Nesta ordem:

   a. **Classifique a foto-semente** — que função ela já ocupa no board. (`11-tech-noir-3`, por
      exemplo, é tipografia/interface.) Essa função sai da lista de busca: já está coberta.

   a1. **Deixe o `--objetivo` reordenar a lista.** `ambiente` puxa espaço, luz e material;
      `campanha` puxa key visual, styling, cor e tipografia; `produto` puxa still life,
      material, packshot e embalagem; `personagem` puxa retrato, figurino, pose e luz de
      personagem. Sem `--objetivo`, use a ordem padrão da tabela.

   b. **Preencha as vagas restantes** pela prioridade de `references/board.md`, parando quando
      completar: hero (o parente mais próximo da semente) → atmosfera/luz → textura/material →
      styling **ou** objetos (o que a semente não for) → ambiente → tipografia/gráfico → uma
      tradução (2D ou 3D, a que o DNA indicar mais forte).

   c. Converta em `plano.json` (formato em `references/board.md`): `category` → `slug`,
      `query` → `busca`. `origem`: `catalogo` para consulta derivada do DNA; `usuario`
      (prefixo `custom-`) só para consulta que a pessoa pediu de viva voz.

   Consulta do DNA que sobrou fora das vagas **não é baixada**. Ela fica registrada no
   `dna.json` e pode virar busca depois, se a pessoa quiser trocar uma peça.

3. **[C] Baixar.** Reusa o coletor da `mood_vibe_scout` — não reescreva:
   ```bash
   .venv/bin/python .claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py --plano plano.json
   ```

4. **[I] Conferir.** Leia as `_folha-contato-N.jpg` com o `Read`. Consulta que voltou fora do
   universo visual → refaça **uma vez** com query mais específica
   (`--refazer <slug> --busca "…"`) e reporte `[decisão] …`. Na segunda falha, siga sem ela.

5. **[I/A] Curar.** A **hero é a foto-semente** — o board nasce dela e é montado em volta dela;
   só troque se a pessoa mandar. Para as outras vagas, aplique o teste de coerência de
   `references/board.md`: cada imagem tem que compartilhar cor/luz **ou** forma/material/época
   com a semente, e ocupar uma função ainda vazia.

   **`--gate interativo`:** mostre a lista final — arquivo, função, uma frase de por que entrou
   — e **pare para aprovação**.

   **`--gate auto`:** não pergunte. Escolha pelo mesmo teste e grave `<saida>/curadoria.md` com
   a lista escolhida **e cada descarte com o motivo** — em especial o descarte que era bonito
   mas abria uma segunda direção de arte. Sem esse arquivo, `auto` não é auditável e a corrida
   não está completa.

   Nos dois modos, o desempate é o mesmo: entre duas candidatas que passam no teste, ganha a
   que fica **na paleta**; entre duas na paleta, ganha a que **não repete** o enquadramento de
   uma célula já escolhida.

6. **[C] Montar a prancha.**
   ```bash
   .venv/bin/python .claude/skills/mood_board_builder/scripts/montar_board.py --board board.json
   ```
   A paleta vem do campo `palette` do DNA (HEX aproximado — diga isso). Saem
   `_moodboard.jpg`, mais o `_indice.json`/`_indice.md` que o coletor já gerou.

7. **[S] Entregar.** Leia a prancha com o `Read` antes de entregar — se uma imagem ficou
   cortada em algo essencial pelo recorte central, troque por outra e remonte. **Isso vale nos
   dois modos de gate:** `auto` não autoriza entregar prancha que você não olhou. Feche dizendo
   o que a direção afirma em 2–3 frases e onde ela ainda está frágil; em `auto`, liste também
   toda troca e todo descarte que teriam sido uma pergunta.

## Regras

- **A semente sempre entra no board**, como hero. O board é a leitura dela, não um board novo
  que por acaso nasceu perto dela.
- **Uma foto-semente por vez.** Se a pessoa apontar várias, pergunte qual é a referência — não
  monte um board com todas dentro.
- **Semelhante ≠ complementar.** 7 variações do mesmo enquadramento não são moodboard. Num
  board de 8, cada função aparece **uma vez só**.
- **Uma tentativa extra por consulta.** Não persiga a query perfeita.
- Query em **inglês**, mesmo conversando em português — o Pinterest indexa muito melhor.
- Não afirme autoria, licença ou "livre para uso" de nada. `origem_url` no `_indice.json` é a
  rastreabilidade; para uso comercial, a pessoa segue o pin até a fonte.
- Paleta amostrada a olho é **aproximada**; nunca apresente como medição.
- Pasta de saída é material local — confirme o `.gitignore` antes de qualquer `git add`.

## Referências

| Arquivo | Quando abrir |
|---|---|
| `references/board.md` | Passos 2, 5 e 6 — categorias, contrato do plano e do board, teste de coerência |
| `.claude/skills/mood_vibe_scout/references/saida.md` | detalhe do `plano.json` e dos prefixos de arquivo |
| `.claude/skills/mood_visual_dna/references/moodboard-curation.md` | curadoria completa (distribuição, pontuação, layout) |
