---
name: mood_vibe_scout
description: >
  Encontra a vibe visual de uma campanha antes da etapa 2 (mood board): entrevista a pessoa
  como um diretor de arte faria, monta uma shortlist cruzando um catálogo de 30 vibes com
  sugestões fora do catálogo, coleta N imagens de referência por vibe no Pinterest (default 3),
  confere o resultado visualmente em folhas de contato e entrega tudo indexado, com prefixo de
  arquivo distinguindo o que a pessoa pediu (`custom-`) do que a skill sugeriu (`extra-`).
  Use quando o usuário quiser pesquisar, explorar ou decidir a vibe/mood/estética de uma
  campanha, buscar referência visual, ou digitar /mood_vibe_scout. Não use para gerar
  imagem (é a etapa 2, `mood`) nem para escrever o prompt de vibe — isto é a pesquisa que vem
  antes.
---

# Encontrar a vibe da campanha (mood_vibe_scout) `[extensão]`

Pesquisa de referência visual: entrevista → shortlist → coleta no Pinterest → conferência
visual → entrega indexada. O produto é **material de decisão** — a pessoa olha as folhas de
contato e escolhe a vibe da campanha.

`[extensão]`: a aula 009 ensina *uma vibe única para a campanha inteira* (1 prompt de vibe ×
grid de 4). Esta skill **não substitui** isso — ela alimenta a decisão de *qual* vibe, que a
aula assume já tomada. Nada aqui gera imagem nem escreve o prompt da etapa 2.

<HARD-GATE>
Uma única parada humana: **aprovar a shortlist** antes de coletar (Passo 3). Depois disso,
tudo é decidido por regra e reportado em uma linha `[decisão] …` — inclusive refazer uma vibe
cuja coleta veio fora do tema. Nunca peça permissão fora dessa parada.

Duas proibições:
- **Não gerar imagem com IA nem gastar crédito Higgsfield.** Esta skill só baixa referência.
- **Não publicar, subir ou enviar as imagens para lugar nenhum.** São imagens de terceiros
  baixadas do Pinterest: uso de referência, local, sem commit (ver `references/saida.md`).
</HARD-GATE>

## Invocação

```
/mood_vibe_scout [descrição livre da campanha] [--n N] [--vibes a,b,c]
                      [--saida DIR] [--sem-entrevista]
```

- `descrição livre`: qualquer coisa que a pessoa já saiba ("perfume masculino, público 25-40,
  quero algo escuro"). É lida **antes** da entrevista e desativa as perguntas já respondidas.
- `--n`: imagens por vibe. **Default 3.** Acima de 8 a busca começa a raspar o fundo da
  relevância — avise e siga assim mesmo se a pessoa confirmar.
- `--vibes`: slugs ou nomes que a pessoa já quer garantidos na shortlist. Entram sempre.
- `--saida`: pasta de destino. Default `processo_manual/moodboard/fotos_vibe`.
- `--sem-entrevista`: pula direto para a shortlist, usando só a descrição livre e `--vibes`.
  Só use quando a pessoa pedir explicitamente ou quando `--vibes` já define tudo.

## Sequência

1. **[I] Ler o que já foi dito.** Descrição livre, `--vibes`, e o histórico da conversa.
   Anote o que já está respondido — não repita nada disso em pergunta.

2. **[I] Entrevistar.** Siga `references/entrevista.md`: postura de diretor de arte, no máximo
   2 rodadas de `AskUserQuestion` (4 perguntas cada) + 1 pergunta aberta sobre referência que a
   pessoa ama. Feche devolvendo sua leitura em 2–3 linhas.

3. **[I] Montar e aprovar a shortlist.** 6–10 vibes, cruzando `references/catalogo.md`
   (as 30) com o banco de sugestões, pela tabela de mapeamento da entrevista. Toda vibe pedida
   pela pessoa entra. Inclua 2–4 sugestões que ela não pediu, ditas como sugestão. Cada linha
   tem uma frase de "por que entrou". Mostre a tabela e **pare para aprovação**.

4. **[C] Escrever o plano e coletar.** Grave `plano.json` no formato de `references/saida.md`
   (atenção ao campo `origem`, que define o prefixo do arquivo) e rode:
   ```bash
   .venv/bin/python .claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py --plano plano.json
   ```
   ~10–15 s por vibe, 3 abas em paralelo. O script já gera índices e folhas de contato.

5. **[I] Conferir com os próprios olhos.** Leia cada `_folha-contato-N.jpg` com o `Read`. Para
   cada vibe, uma pergunta só: *as imagens são a vibe, ou o Pinterest entendeu a query ao pé da
   letra?* Erro clássico: `clay 3d art` devolvendo fotos de cerâmica real.
   - Fora do tema → refaça **uma vez**, com query mais específica:
     ```bash
     … --plano plano.json --refazer <slug> --busca "<query melhor>"
     ```
     Reporte `[decisão] refiz <vibe>: <query antiga> trazia <o que veio>`.
   - Ainda fora do tema na segunda → mantenha e registre a ressalva no resumo. Não insista.
   - Vibe incompleta (menos de `n` imagens) → refaça uma vez; se persistir, registre.

6. **[I] Entregar.** Resumo com: pasta, total de imagens, legenda dos prefixos, o que foi
   refeito e por quê, e — o mais útil — **quais 3–5 vibes ficaram mais fortes e por quê**.
   "Mais forte" = as 3 imagens da vibe são coerentes entre si; é isso que vira prompt de vibe
   depois. Diga também quais vieram dispersas.

## Regras

- **Nunca invente a query.** Vibe do catálogo usa a query do catálogo (as correções conhecidas
  já estão lá). Vibe nova: monte `<termo da vibe> + <eixo>`, onde eixo é `photography`,
  `aesthetic`, `moodboard`, `poster`, `illustration`, `3d render`, `editorial`, `interior`,
  `character design`, `fashion` ou `background`. Query em **inglês** — o Pinterest indexa muito
  melhor assim, mesmo com a pessoa falando português.
- **Prefixo é contrato com a aplicação**, não enfeite: `custom-` só para vibe que a pessoa
  pediu e que não existe no catálogo; vibe pedida que já é do catálogo entra como catálogo, com
  o número dela. Detalhe em `references/saida.md`.
- **Uma tentativa extra por vibe, no máximo.** Perseguir a query perfeita gasta mais tempo do
  que a pessoa ganha olhando uma vibe a mais.
- Texto para a pessoa em pt-BR; slug, query e nome de arquivo em inglês/ASCII.
- Rodar sempre com o Python do repo (`.venv/bin/python`) — precisa de `playwright` e `Pillow`.
  Se o Chromium não estiver instalado: `.venv/bin/python -m playwright install chromium`.
- A pasta de saída é material local. Confirme que está no `.gitignore` antes de qualquer
  `git add` na pasta.

## Referências

| Arquivo | Quando abrir |
|---|---|
| `references/entrevista.md` | Passos 2 e 3 — perguntas, postura e mapa resposta → vibe |
| `references/catalogo.md` | Passo 3 — as 30 vibes e o banco de sugestões |
| `references/saida.md` | Passo 4 — formato do plano, nomes, prefixos, JSON |
