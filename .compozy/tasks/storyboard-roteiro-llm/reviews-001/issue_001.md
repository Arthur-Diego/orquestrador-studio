---
provider: manual
pr:
round: 1
round_created_at: 2026-08-31T02:38:16Z
status: resolved
file: tests/test_storyboard_view.py
line: 465
severity: high
author: claude-code
provider_ref:
---

# Issue 001: teste T3.8 quebra `make verify` assim que a branch entrar em develop

## Review Comment

`test_t3_8_escrita_de_cena_so_pelo_put_scenes_existente` compara o `view.js` atual com a
versão devolvida por `view_js_antes_da_feature()`, que faz:

```python
base = subprocess.run([git, "-C", str(root), "merge-base", "develop", "HEAD"], ...)
antes = subprocess.run([git, "-C", str(root), "show", f"{base}:studio/etapas/storyboard/view.js"], ...)
```

Na branch `feature/storyboard-roteiro-llm` isso resolve para `29a10a3` (o ponto de fork) e o
teste passa. **Depois do merge em `develop` o `merge-base develop HEAD` passa a ser o próprio
HEAD**, então `antes == js` e a asserção da linha 465

```python
assert js.count('method: "POST"') == antes.count('method: "POST"') + 1
```

vira `18 == 19` e **falha**. Verificado: `view.js` tem hoje 18 ocorrências de `method: "POST"`;
simulando `antes = js` (o cenário pós-merge) a asserção dá `False`.

O mesmo acontece em qualquer branch nova cortada de `develop` depois do merge (o fork point já
contém a feature) e na promoção `develop → main`. Ou seja: o teste é verde exatamente uma vez —
nesta branch — e depois deixa o `make verify` vermelho no tronco, que é justamente onde o gate
de CI roda.

As duas asserções do laço anterior (`url("/scenes")` e `method: "PUT"`, contagens IGUAIS)
sobrevivem ao merge; o problema é só a asserção de delta `+ 1`. O `test_t3_13` também usa
`merge-base` mas compara diff vazio, então continua correto.

Sugestão de correção (qualquer uma resolve, sem perder o que o teste protege):

- trocar a asserção de delta por uma asserção absoluta e independente de git: o `view.js`
  inteiro não pode ter nenhum `method: "POST"`/`method: "PUT"` apontando para `url("/scenes")`
  fora do `saveScenes` já existente, e dentro do `bloco_roteiro(js)` o único `method: "POST"`
  é o de `url("/script/generate")` (isso já é asserido nas duas últimas linhas do teste, que
  não dependem do git); ou
- manter a comparação com o passado, mas fazer `pytest.skip` quando
  `merge-base develop HEAD == git rev-parse HEAD` (ou quando o `antes` já contém o marcador
  `SCRIPT_BLOCK_START`), porque nesse caso não existe "estado anterior à feature" para comparar.

## Triage

- Decision: `ACCEPTED`
- Notes:

**Válida.** Causa raiz: a asserção da linha 465 media um DELTA contra o `view.js` do
`merge-base develop HEAD`. Esse ponto de referência só existe enquanto a branch está fora do
tronco: depois do merge em `develop` (e em qualquer branch cortada dali, e na promoção
`develop → main`) o fork point passa a conter a feature, `antes == js`, e `18 == 18 + 1` fica
falso. O teste seria verde exatamente uma vez, e vermelho justamente onde o gate de CI roda.

**Correção aplicada** (primeira sugestão da issue — asserções ABSOLUTAS, sem `pytest.skip`, que
desligaria no tronco o teste que deveria proteger o tronco):

- `tests/test_storyboard_view.py::test_t3_8_escrita_de_cena_so_pelo_put_scenes_existente` passou a
  asserir, só sobre o `view.js` de hoje:
  - (a) dentro de `bloco_roteiro(js)` existe exatamente UM `method: "POST"` e a linha dele contém
    `url("/script/generate")` (a asserção lê a linha inteira da chamada `api(...)`, então o POST
    tem de ser aquele, não um POST qualquer que por acaso conviva com a string no bloco);
  - `'"/scenes"' not in bloco` e `'method: "PUT"' not in bloco` — o bloco não monta rota nem verbo
    de escrita de cena próprios;
  - (b) no arquivo INTEIRO, toda ocorrência de `url("/scenes")` ou é leitura (linha sem `method:`)
    ou é o `method: "PUT"` do contrato, e nenhuma delas cai entre `SCRIPT_BLOCK_START` e
    `SCRIPT_BLOCK_END` — ou seja, o bloco do roteiro não abre um segundo caminho de escrita.
- `view_js_antes_da_feature()` ficou sem uso e foi REMOVIDO. `test_t3_13` não o usava (tem a sua
  própria chamada a `merge-base` comparando diff VAZIO, que continua correta depois do merge) e
  ficou intocado. No lugar do helper entrou `linha_de(js, i)`, que só fatia a linha do índice.

**Prova de que sobrevive ao merge** (cenário pós-merge simulado, não estimado): clone do worktree
em `/tmp/.../postmerge` com `git checkout -B develop` no próprio HEAD, de modo que
`git merge-base develop HEAD == git rev-parse HEAD == 905a694` (exatamente o estado pós-merge que
quebrava a asserção antiga). Nesse clone, `pytest tests/test_storyboard_view.py` → **53 passed**,
com `-k "t3_8 or t3_13"` → **3 passed** (nenhum skip). Além disso, o corpo do `test_t3_8` não cita
`git`, `merge-base`, `subprocess` nem `skip` em asserção alguma — a única menção é na docstring,
explicando por que a comparação com o passado saiu.
