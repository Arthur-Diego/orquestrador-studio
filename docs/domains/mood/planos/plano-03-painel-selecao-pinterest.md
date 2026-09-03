# Plano 03 — Painel de seleção das fotos de vibe do Pinterest

Task-Id: `ADH-OS-20260902-03`
Status: **plano** — nada implementado.
Data: 2026-09-02

---

## 1. O que se quer

Depois de pesquisar vibes no Pinterest (`mood_vibe_scout`), ver o resultado **dentro da tela de
mood boards**, num painel paginado de até **20 fotos por página**. O usuário marca as que quer,
salva, e elas vão para **fotos escolhidas**. É dessa pasta — e só dela — que a funcionalidade
do orquestrador (Plano 01) é chamada.

Fluxo completo:

```
/mood_vibe_scout  →  fotos_vibe/ (N por vibe, indexadas)
                          ↓
              PAINEL PAGINADO (20 por página)     ← este plano
                          ↓  marcar + salvar
                   fotos_escolhidas/
                          ↓
             "Gerar mood com as skills"           ← Plano 01
```

## 2. O que já existe (verificado)

| Peça | Onde | Observação |
|---|---|---|
| Coletor Pinterest | `.claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py` | grava `NN-<slug>-K.jpg`, `_indice.json`/`.md`, `_folha-contato-N.jpg`. Prefixos: sem prefixo = catálogo, `custom-` = pedida, `extra-` = sugerida. |
| Saída padrão | `processo_manual/moodboard/fotos_vibe/` | hoje fora da árvore da tela |
| Escolhidas | `processo_manual/moodboard/fotos_escolhidas/` | hoje **preenchida à mão** pelo usuário |
| Grade de candidatas na tela | `studio/moodboards/service.py:candidates` + `select` (`MAX_SELECTED = 8`) | precedente de UI de seleção — **mas com teto de 8 e semântica diferente** |
| Servir arquivo | mount `/mbfiles` → `MOODBOARDS_DIR` | `processo_manual/` **não** é servido hoje |

## 3. Os buracos

1. **Nada serve `fotos_vibe/` para o browser.** Só `MOODBOARDS_DIR` e `PROJECTS_DIR` estão
   montados. Sem resolver isso, o painel não tem o que exibir.
2. **`select` existente não serve.** Ele tem teto de 8 e significa "as 8 do board"; aqui a
   seleção é "a peneira", que pode ter dezenas e não vira board.
3. **Não há paginação em lugar nenhum da tela.** É componente novo.

## 4. Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D1 | Onde ficam `fotos_vibe`/`fotos_escolhidas` | (a) mover para `moodboards/_vibes/` e `moodboards/_escolhidas/`; (b) manter em `processo_manual/` e montar uma rota estática nova | **(a)** — uma raiz gitignored só, já montada em `/mbfiles`, sem expor `processo_manual/` inteiro ao browser |
| D2 | Paginação | servidor (offset/limit) | **servidor** — a pasta pode ter centenas; `?page=&per_page=` com `per_page` **máx. 20** |
| D3 | Salvar = copiar ou mover | copiar | **copiar** — `fotos_vibe/` é o resultado da pesquisa e não deve ser destruído ao escolher |
| D4 | Deduplicação | por hash do arquivo | **sim** — a mesma foto pode vir em duas vibes |
| D5 | Teto de escolhidas | sem teto | **sem teto** — é peneira, não board; o teto de 8 é do board, não daqui |
| D6 | Agrupar por vibe | filtro por vibe lido do `_indice.json` | **sim** — sem isso 200 fotos viram sopa |

## 5. Escopo

### Entra
- `studio/moodboards/vibes.py` **[novo]** — leitura de `_indice.json`, listagem paginada
  (com `vibe`, `origem` do prefixo, `origem_url`), cópia para escolhidas, deduplicação por
  hash, remoção de uma escolhida.
- Endpoints em `studio/moodboards/router.py`:
  - `GET    /api/vibes?page=&per_page=&vibe=&origem=` → `{items, page, per_page, total, pages}`,
    `per_page` limitado a 20;
  - `GET    /api/vibes/facets` → vibes disponíveis + contagem, para o filtro;
  - `POST   /api/vibes/select` → `{ids: [...]}` copia para escolhidas, devolve o que entrou e o
    que era duplicata;
  - `GET    /api/escolhidas` → paginado igual;
  - `DELETE /api/escolhidas/{id}` → tira da peneira (não apaga de `fotos_vibe`).
- Front (`studio/web/moodboards.js` + CSS): grade de 20 com thumb, nome, vibe e badge de origem
  (catálogo / pedida / sugerida); marcação múltipla com "marcar todas da página"; contador de
  selecionadas persistente **entre páginas**; barra de paginação; filtro por vibe; painel
  "fotos escolhidas" com remoção; e o botão do Plano 01 habilitado **só** quando há pelo menos
  uma escolhida.
- Testes: paginação (bordas: página 0, além do fim, `per_page > 20`), filtro, cópia,
  duplicata, remoção, pasta vazia, `_indice.json` ausente ou corrompido.
- FDD + HLD do domínio `mood`.

### Não entra
- Buscar no Pinterest a partir da tela (é o Plano 04 + Plano 01).
- Editar imagem, recortar ou anotar.
- Subir as imagens para qualquer lugar.
- Mexer no `select`/`MAX_SELECTED` do board.

## 6. Passos

1. Decidir D1 (é o que destrava tudo) e registrar em ADR se mudar o layout de diretórios.
2. FDD com o contrato de paginação e a matriz de erros.
3. `vibes.py` + testes com fixtures de pasta (sem rede).
4. Endpoints + coleção Postman do domínio.
5. Front: grade, paginação, filtro, seleção persistente, painel de escolhidas.
6. Ligar com o Plano 01 (botão habilitado por escolhida).
7. `make verify`, QA da tela, PR pelo gate `ft-pr`.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Expor `processo_manual/` inteiro ao browser | D1 recomenda raiz dedicada; nunca montar `processo_manual/` |
| Seleção perdida ao trocar de página | estado no front por id, com teste de UI |
| Pasta com centenas de arquivos derrubando a tela | paginação no servidor + thumbs, nunca a imagem cheia na grade |
| Nome de arquivo virando caminho | validar id contra regex, como `MBID_RE` já faz |
| Imagem de terceiros entrando no git | raiz gitignored + teste |

## 8. Critérios de aceite

- O painel mostra no máximo 20 por página e navega até o fim sem perder a seleção.
- Filtrar por vibe funciona e o contador bate com `_indice.json`.
- Salvar copia para escolhidas **sem remover** de `fotos_vibe`, e duplicata é reportada, não duplicada.
- Remover de escolhidas não apaga o original.
- Com a pasta vazia, a tela explica o que fazer (rodar `mood_vibe_scout`) em vez de quebrar.
- O botão de gerar mood só habilita com pelo menos uma escolhida.
- `make verify` verde; nenhum teste toca a rede.
