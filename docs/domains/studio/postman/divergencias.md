# Divergências: FDD × contrato publicado — `prompter-presets-realismo`

**Contrato publicado**: não existe `openapi.yaml`/`openapi.json` neste repositório nem em
repositórios irmãos do workspace (busca por glob `openapi*.{yaml,yml,json}` até profundidade 3 na
raiz do projeto, nos irmãos `../*-contracts*` e em `node_modules/@*/contracts*`: nenhum resultado).
O app é FastAPI e expõe o schema em runtime (`/openapi.json`), mas nada é versionado. Na ausência
de contrato publicado, o cruzamento foi feito **FDD × implementação** (`studio/creditos/router.py`,
`studio/common/settings.py`, `studio/common/prompter.py`), que é o único contrato efetivo hoje.

Nenhuma divergência de severidade **ALTA**: todas as rotas da §5 existem, com os métodos e os
status declarados.

| Severidade | O que o FDD diz | O que a implementação diz | Fontes |
|---|---|---|---|
| MEDIA | §5 L334: `GET /api/prompter/presets` — "**200 sempre** (catálogo em memória). Query opcional `pid` para resolver defaults do projeto." Não prevê 404 nesta rota; a linha de 404 da §6 fala em "`pid` inexistente nas **rotas de projeto**", e esta é uma rota global com query. | `router.py:158-160` chama `project_dir(pid)` quando `?pid=` vem preenchido, então `?pid=<inexistente>` devolve **404**, não 200. | FDD L331-334 e L385 · `studio/creditos/router.py:154-161` |
| MEDIA | §5 L359 declara a rota `GET /api/prompter/preset-config` (global) mas **não fixa o shape da resposta**; o único shape descrito no bloco é o do PUT ("devolve `preset_default_for(kind)`", L360). | `router.py:164-166` devolve `{"defaults": {ação: {preset, source}}}` — um mapa aberto sem `pid`, e não um `{kind, preset, source}`. Coerente com a amenda A1, porém não declarado. | FDD L359-361 · `studio/creditos/router.py:164-166` |
| MEDIA | §5 L363-365 prevê `DELETE` de override **apenas por projeto**. Para o escopo global há só `GET` e `PUT`; e como `preset: null` gravado é escolha explícita que **encerra a cadeia** (L327-329, `source: "global"`), não existe caminho de API para voltar `source` a `"code"`. | `settings.set_global_preset` grava a chave; nenhuma rota remove a chave do `config.json` global. Consequência prática: rodar a coleção deixa estado residual, desfeito só editando `STATE_DIR/config.json` à mão. | FDD L314-329 e L359-365 · `studio/common/settings.py:272-293` |
| BAIXA | §5 L294-296 diz que "campos comuns a **todo preset**" incluem `fidelity` (vocabulário fixo da skill) e `negative`. | O catálogo HTTP (`router.py:126-133`) projeta `id, name, default, desc_pt, rig, light, grade, negative` — sem `fidelity`. Não é contradição real: o exemplo de resposta da própria §5 (L336-352) também omite `fidelity`, e o campo é do dict `REALISM_PRESETS` (§9 critério 1), não da resposta. Ruído documental. | FDD L294-296 e L336-352 · `studio/creditos/router.py:126-133` |

## Como a coleção lida com cada uma

- **404 no `?pid`**: há um request dedicado em `erros/` asserindo **404** (o comportamento
  implementado), com aviso no script caso volte 200 — nesse caso quem está certo é a §5 e a
  divergência se resolve pelo outro lado.
- **Shape do `GET preset-config`**: o teste assere o `{"defaults": ...}` implementado e a descrição
  do request registra que a §5 é omissa.
- **Sem `DELETE` global**: documentado no README (seção "Efeito colateral: a coleção ESCREVE
  estado"), com a instrução de limpeza manual.
- **`fidelity`**: não asserido nem exigido — a coleção valida o shape do exemplo da §5.
