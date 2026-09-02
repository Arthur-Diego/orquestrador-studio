# Contrato de saída

Tudo que a skill produz cai em **uma pasta só** (default
`processo_manual/moodboard/fotos_vibe/`). A aplicação que consumir isso lê `_indice.json`;
os nomes de arquivo são o mesmo dado, redundante de propósito, para funcionar mesmo quando
alguém só abre o Finder.

## Nome do arquivo — o prefixo é o contrato visual

```
<prefixo><NN>-<slug>-<i>.jpg
```

| Prefixo | `origem` no JSON | Significa | Badge sugerido na UI |
|---|---|---|---|
| _(vazio)_ | `catalogo` | uma das 30 vibes do catálogo | neutro / cinza |
| `custom-` | `usuario` | **a pessoa pediu essa vibe** | destaque forte |
| `extra-` | `sugestao` | a skill propôs, fora do catálogo | destaque suave |

```
10-matrix-core-1.jpg              → catálogo #10, 1ª imagem
custom-01-blade-runner-2049-3.jpg → pedido da pessoa, 3ª imagem
extra-02-analog-35mm-1.jpg        → sugestão da skill, 1ª imagem
```

- `NN` é sequencial **dentro de cada origem** (catálogo usa o número do catálogo; `custom-` e
  `extra-` recomeçam em 01), com dois dígitos, para a ordem alfabética bater com a ordem da
  shortlist.
- `slug`: minúsculas, hífen, sem acento — é identificador, fica em inglês quando a vibe é um
  termo em inglês, e em português quando a pessoa nomeou em português.
- `i` vai de 1 a `n_por_vibe`.
- Sempre `.jpg`. O Pinterest serve `736x` como maior tamanho público; `originals` responde 403.

**Nunca** renomeie um arquivo já entregue só para mudar de prefixo: o app pode ter referência
salva. Recolete a vibe com o prefixo certo e apague a versão antiga.

## `_indice.json`

```jsonc
{
  "campanha": "perfume masculino, público 25-40, lançamento de verão",
  "n_por_vibe": 3,
  "legenda_prefixo": { "sem prefixo": "...", "custom-": "...", "extra-": "..." },
  "vibes": [
    {
      "num": 10,
      "slug": "matrix-core",
      "nome": "Matrix Core",
      "tipo": "Realista/Tecnológica",
      "busca": "matrix aesthetic fashion",
      "origem": "catalogo",              // catalogo | usuario | sugestao
      "porque": "você pediu pegada digital e essa é a leitura mais literal dela",
      "candidatas": 20,                   // quantos pins a busca ofereceu
      "salvas": [
        { "arquivo": "10-matrix-core-1.jpg",
          "origem_url": "https://i.pinimg.com/736x/...jpg",
          "bytes": 84213 }
      ]
    }
  ]
}
```

`origem_url` é a rastreabilidade da imagem — de onde veio, para creditar ou voltar ao pin.

## Demais arquivos

| Arquivo | O que é |
|---|---|
| `_indice.md` | a mesma tabela, legível por humano, com a legenda dos prefixos |
| `_folha-contato-N.jpg` | 10 vibes por folha, 3 miniaturas por linha, rótulo com nome/origem/query — é o que você **lê com o Read** para conferir se a coleta prestou |
| `plano.json` | o plano executado (entrada do script), guardado para permitir `--refazer` |

## O plano

O script é dirigido por um `plano.json` — escreva-o **antes** de rodar, a partir da shortlist
aprovada:

```jsonc
{
  "saida": "processo_manual/moodboard/fotos_vibe",
  "n_por_vibe": 3,
  "campanha": "texto livre",
  "vibes": [
    { "num": 10, "slug": "matrix-core", "nome": "Matrix Core",
      "tipo": "Realista/Tecnológica", "busca": "matrix aesthetic fashion",
      "origem": "catalogo", "porque": "..." }
  ]
}
```

O script reescreve esse arquivo com `candidatas`/`salvas` preenchidos, então ele vira também o
registro do que foi feito.

## Comandos

```bash
# coleta completa
.venv/bin/python .claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py --plano plano.json

# refazer uma vibe que veio ruim, com query melhor
… --plano plano.json --refazer clay-3d --busca "clay render 3d character illustration"

# só remontar índices e folhas de contato (não baixa nada)
… --plano plano.json --so-folhas
```

Garantias do script: dedupe global por md5 (nenhuma imagem repetida entre vibes), descarte de
arquivo abaixo de 8 KB (ícone/placeholder), 3 abas em paralelo, e uma vibe que falha não
derruba as outras.

## Onde isso vive

A pasta de saída é **material local**, como `projects/` e `media/`: imagem de terceiro baixada
do Pinterest não entra em commit. Se a pasta de saída estiver dentro do repo, confirme que ela
está no `.gitignore` antes de qualquer `git add`.
