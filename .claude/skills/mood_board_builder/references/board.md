# Categorias, contratos e curadoria

## Categorias de um board

Um moodboard não é uma pilha de imagens parecidas — é um sistema visual. Para 12 referências
(board grande):

| Função | slug | Quantas | Modificadores úteis na query |
|---|---|---|---|
| Hero | `hero` | 1 | `cinematic`, `editorial`, `key visual` |
| Ambiente / arquitetura | `ambiente` | 2 | `interior`, `environment`, `architecture` |
| Atmosfera / luz | `atmosfera` | 1–2 | `mood lighting`, `haze`, `backlight` |
| Styling / personagem | `styling` | 1 | `fashion editorial`, `lookbook`, `costume` |
| Objetos / props | `objetos` | 1 | `still life`, `product`, `vintage tech` |
| Textura / material | `textura` | 2 | `texture`, `material study`, `macro` |
| Tipografia / gráfico | `tipografia` | 1 | `poster`, `type system`, `monospace` |
| Interface / digital | `interface` | 0–1 | `UI`, `HUD`, `terminal` |
| Tradução 2D | `traducao-2d` | 1 | `2D illustration`, `graphic novel`, `cel animation` |
| Tradução 3D | `traducao-3d` | 1 | `3D render`, `CGI`, `material study` |

## Board de 8 (o default) — ordem de prioridade

A tabela acima é o board grande. Para um board de 8 a semente ocupa uma vaga e sobram **7**.
Corte a lista nesta ordem, uma imagem por função:

| Vaga | Função | Por que nessa posição |
|---|---|---|
| 1 | `hero` | o parente mais próximo da semente — ancora a direção |
| 2 | `atmosfera` | luz e clima; é o que faz o board respirar |
| 3 | `textura` | a superfície é o sinal que mais some se ficar de fora |
| 4 | `styling` **ou** `objetos` | o que a semente **não** for |
| 5 | `ambiente` | dá lugar à direção |
| 6 | `tipografia` | a voz gráfica |
| 7 | tradução `2d` **ou** `3d` | a que o DNA indicar mais forte |

Antes de cortar, **tire da lista a função que a semente já ocupa**. Board maior que 8: continue
descendo a tabela grande. Ajuste ao projeto — campanha pede styling e luz; interiores pedem
espaço e material.

## Três camadas de consulta

Para cada função, monte a query em uma destas camadas — misturar as três é o que impede o
board de virar 8 fotos do mesmo enquadramento:

1. **Âncora** — preserva vibe principal + assunto. `tech noir cinematic portrait green light`
2. **Atributo** — isola cor, luz, textura ou material. `phosphor green CRT glow macro`
3. **Tradução** — leva a linguagem para outra modalidade. `tech noir 3D render black chrome`

Fórmula: `[vibe] + [modalidade] + [assunto] + [luz/cor] + [material/época]`, 3 a 6 componentes.

Para fugir de cópia de franquia, troque o nome da obra por seus sinais:
`Matrix` → `late-90s tech noir`, `phosphor green`, `black leather`, `CRT`, `digital rain`.

## `plano.json` (entrada do coletor)

```jsonc
{
  "saida": "processo_manual/moodboard/board-tech-noir",
  "n_por_vibe": 3,
  "campanha": "expansão do DNA de 11-tech-noir-1.jpg",
  "vibes": [
    { "num": 1, "slug": "hero", "nome": "Hero", "tipo": "âncora",
      "busca": "tech noir cinematic portrait green practical lighting",
      "origem": "catalogo", "porque": "assunto e luz da imagem escolhida" }
  ]
}
```

`num` é sequencial na ordem da tabela acima (vira o prefixo `01-`, `02-`… no arquivo).
`origem`: `catalogo` = consulta derivada do DNA (sem prefixo); `usuario` = a pessoa pediu essa
consulta na hora (prefixo `custom-`). Contrato completo dos prefixos em
`.claude/skills/mood_vibe_scout/references/saida.md`.

## `board.json` (entrada do montador)

```jsonc
{
  "titulo": "Perfume X — direção de arte",
  "subtitulo": "tech noir · 8 referências · paleta aproximada",
  "base": "processo_manual/moodboard/board-tech-noir",   // onde estão os .jpg
  "saida": "processo_manual/moodboard/board-tech-noir",  // onde gravar a prancha
  "arquivo": "_moodboard.jpg",
  "fundo": "escuro",                    // escuro | claro
  "largura": 1800,
  "legendas": true,
  "paleta": ["#0B0F0C", "#12351F", "#39FF88", "#C9D6CE"],   // 4 a 8, do DNA
  "hero": "01-hero-1.jpg",
  "legenda_hero": "hero · tech noir",
  "imagens": [ { "arquivo": "02-ambiente-1.jpg", "legenda": "ambiente" } ]
}
```

A hero ocupa 2×2 células no canto superior esquerdo; as demais preenchem a grade de 4 colunas
em ordem. Cada imagem é **recortada ao centro** para preencher a célula — por isso confira a
prancha depois de montar: um recorte pode comer o assunto.

## Teste de coerência

Cada candidata precisa responder **sim** a pelo menos duas:

- compartilha família de cor ou temperatura com a imagem escolhida?
- compartilha a lógica de iluminação?
- compartilha forma, material ou época?
- reforça a mesma emoção?
- ocupa uma função ainda vazia no board?

Fora isso: remova o que é bonito mas abre uma **segunda direção de arte** sem intenção. Se
sobrarem duas direções igualmente fortes, entregue dois boards separados em vez de misturar.

## Diagnóstico antes de fechar

- assunto repetido demais
- falta textura, tipografia ou material
- paleta fragmentada
- mistura acidental de épocas
- várias imagens disputando o papel de hero
- alguma referência sem `origem_url` no índice
