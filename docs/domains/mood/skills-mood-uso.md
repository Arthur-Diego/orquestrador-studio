### Skills `mood_` — guia de uso `[extensão]`

Pesquisa de referência visual que vem **antes** da etapa 2. Monta uma prancha de moodboard com
imagens do Pinterest para você olhar e decidir a direção de arte.

Não gera imagem com IA, não gasta crédito Higgsfield, não escreve o prompt de vibe da aula 009
e não commita nada. As imagens são referências de terceiros: uso local.

---

### Qual skill eu uso?

```
Você já escolheu uma foto de referência?
│
├── NÃO ──► /mood_vibe_scout
│           entrevista sobre a campanha → shortlist de vibes → 3 fotos de cada
│           saída: fotos_vibe/ + folhas de contato para você escolher UMA
│           │
│           └──► escolheu uma foto? desce pro NÃO virou SIM ↓
│
└── SIM ──► /mood_orquestrador          ← é este que você chama no dia a dia
            │                            (um board por objetivo pedido)
            ├─ 1. QUAL foto + QUAIS objetivos     [pergunta] ou [--foto --objetivo]
            │
            ├─ 2. chama mood_visual_dna — um DNA por objetivo
            │     lê a foto e devolve dna.json: vibe, paleta HEX, 7 consultas por função
            │     │
            │     └─ a leitura                    [PARA] ou [grava leitura.md e segue]
            │
            ├─ 3. chama mood_board_builder — um board por objetivo
            │     baixa 7 consultas × 3 candidatas = 21 imagens por board
            │     │
            │     └─ a curadoria                  [PARA] ou [grava curadoria.md e segue]
            │
            └─ 4. monta, confere o recorte e entrega _moodboard.jpg + _run.json
```

Os dois `[PARA]` acontecem com `--gate interativo` (default); com `--gate auto` viram registro
em arquivo e a corrida vai até o fim sozinha.

As duas skills do meio (`mood_visual_dna` e `mood_board_builder`) também rodam sozinhas, se
você quiser só um pedaço. O caminho normal é chamar só o `/mood_orquestrador`.

---

### O que cada uma faz

| Skill | Entra | Sai |
|---|---|---|
| `mood_vibe_scout` | uma conversa sobre a campanha | N fotos de cada vibe da shortlist, indexadas |
| `mood_visual_dna` | **uma** foto | `dna.json`: vibe + confiança, paleta HEX aproximada, consultas por função |
| `mood_board_builder` | `dna.json` | busca, baixa, cura e monta `_moodboard.jpg` |
| `mood_orquestrador` | nada — ele pergunta | encadeia as três acima numa corrida só |

---

### Regra que manda em tudo

**Um board nasce de UMA foto.** A pasta de escolhidas é a sua peneira, não o conteúdo do board.
A foto-semente vira a hero da prancha e as outras 7 vagas são preenchidas por função. Quer
explorar 3 fotos? São 3 rodadas e 3 boards separados.

**O objetivo muda o board, não a foto.** A mesma semente rende boards diferentes conforme o
objetivo (ambiente/cenário, conceito de campanha, produto, personagem): o objetivo é o que
decide quais funções entram nas 7 vagas e como as consultas são escritas. Rodar a mesma foto
com objetivos diferentes é uma forma legítima de comparar direções — por isso a pasta leva o
objetivo no sufixo: `board-<slug-da-vibe>-<objetivo>/`.

A conta do tamanho:

```
consultas = --board - 1        (a semente já ocupa uma vaga)
downloads = consultas × --n
```

Board de 8 (default) → 7 consultas × 3 candidatas = 21 downloads, 7 entram na prancha.

---

### Argumentos

```
/mood_orquestrador [ARQUIVO|TRECHO|DIRETÓRIO] [--objetivo LISTA|todos] [--gate interativo|auto]
                   [--n N] [--board N] [--saida DIR] [--fundo escuro|claro] [--params ARQ.json]
```

| Argumento | Valores | Default | O que faz |
|---|---|---|---|
| foto | caminho, trecho de nome ou diretório | pergunta | a foto-semente |
| `--objetivo` | `ambiente` · `campanha` · `produto` · `personagem` · lista com vírgula · `todos` | pergunta | quais boards gerar — **um por objetivo** |
| `--gate` | `interativo` · `auto` | `interativo` | se as paradas humanas acontecem |
| `--board` | inteiro ≥ 4 | `8` | quantas referências na prancha |
| `--n` | inteiro ≥ 1 | `3` | candidatas por consulta — é o que permite curar |
| `--saida` | diretório | `processo_manual/moodboard/` | raiz; cada objetivo ganha `board-<slug>-<objetivo>/` |
| `--fundo` | `escuro` · `claro` | `escuro` | tema da prancha |
| `--params` | caminho de JSON | — | mesmas chaves, para chamada programática |

A `mood_board_builder` aceita os mesmos `--objetivo` (um só) e `--gate`, para quando você quiser
rodar só a etapa de montagem.

### Os quatro objetivos

O objetivo não é rótulo: é o que decide **quais funções ocupam as 7 vagas**. Mesma foto,
objetivos diferentes, boards diferentes.

| `--objetivo` | A pergunta que o board responde |
|---|---|
| `ambiente` | onde a história acontece? |
| `campanha` | o que a campanha afirma? |
| `produto` | como o objeto existe nesse mundo? |
| `personagem` | quem vive nesse mundo? |

Quando a semente não contém o assunto do objetivo (uma paisagem pedida como `produto`), o board
é **extrapolação de cor, luz e material**, não leitura — e a entrega diz isso.

### Gate: interativo × automático

| | `interativo` (default) | `auto` |
|---|---|---|
| qual foto | pergunta | vem de `--foto`; sem ela, para e avisa |
| aprovar a leitura | mostra e para | grava `leitura.md` e segue |
| aprovar a curadoria | mostra e para | grava `curadoria.md` (escolhidas **e** descartes com motivo) e segue |

`auto` desliga a **pergunta**, não a regra: as mesmas decisões são tomadas com o mesmo critério,
gravadas em arquivo e listadas na entrega. O que **nunca** muda com o gate: não gera imagem com
IA, não gasta crédito Higgsfield, não publica nada, não afirma licença, não olha a foto pelo
nome e não entrega prancha sem ter conferido o recorte.

### Chamada programática

```json
{
  "foto": "processo_manual/moodboard/fotos_escolhidas/23-anime-city-night-3.jpg",
  "objetivo": ["ambiente", "campanha"],
  "gate": "auto",
  "board": 8, "n": 3,
  "saida": "processo_manual/moodboard",
  "fundo": "escuro"
}
```

A corrida grava `<saida>/_run.json` com a semente, o gate, os downloads e, por board, a pasta,
a prancha, quantas imagens entraram, o que foi refeito e o que foi trocado. É esse arquivo que a
tela lê de volta.

### A conta antes de baixar

```
consultas por board = --board - 1
downloads           = objetivos × consultas × --n
```

`--objetivo todos --board 8 --n 3` = 4 × 7 × 3 = **84 downloads**.

---

### O que fica no disco

```
processo_manual/moodboard/
├── _run.json                       ← manifesto da corrida (o que a tela lê de volta)
└── board-<slug>-<objetivo>/
    ├── _moodboard.jpg              ← a prancha
    ├── _folha-contato-N.jpg        ← as 21 candidatas, com a query no cabeçalho
    ├── _indice.json / .md          ← origem_url de cada pin (rastreabilidade até a fonte)
    ├── dna.json                    ← DNA visual da semente PARA ESTE objetivo
    ├── plano.json                  ← as consultas que foram baixadas
    ├── board.json                  ← a curadoria + paleta + layout
    ├── leitura.md                  ← só em --gate auto: a leitura que não foi revisada
    ├── curadoria.md                ← só em --gate auto: escolhidas e descartes com motivo
    └── NN-<funcao>-K.jpg           ← as candidatas
```

`processo_manual/` **não está no `.gitignore`** — confirme antes de qualquer `git add`.

---

Detalhe de cada skill: `.claude/skills/mood_*/SKILL.md`. A etapa 2 propriamente dita está em
`docs/domains/mood/hld.md`.
