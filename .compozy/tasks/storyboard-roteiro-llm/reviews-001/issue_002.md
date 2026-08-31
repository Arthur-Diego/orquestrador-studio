---
provider: manual
pr:
round: 1
round_created_at: 2026-08-31T02:38:16Z
status: resolved
file: studio/storyboard/service.py
line: 1209
severity: medium
author: claude-code
provider_ref:
---

# Issue 002: o servidor não confere o rig do preset no `image_prompt` devolvido

## Review Comment

O FDD (`_techspec.md` §5, fluxo principal, passo 5) atribui ao SERVIÇO a validação da resposta:

> "Serviço valida/normaliza a resposta (N cenas, `text` pt-BR truncado em 500, prompt de imagem
> não vazio **contendo o rig do preset**)"

e o critério de aceite 3 (`[cross-feature]`, amenda A9) cobra que "o rig do preset escolhido
(corpo + lente + formato de `REALISM_PRESETS[id]['rig']`) apareça **literalmente** no
`image_prompt` de **cada** cena gerada".

Na implementação essa metade não existe:

- `prompter._parse_script` (`studio/common/prompter.py:521`) valida a fence JSON, a contagem de
  cenas, `text` e `image_prompt` não vazios — mas nunca olha o rig;
- `sb._script_payload` (`studio/storyboard/service.py:1209`) só trunca `text` em
  `MAX_SCENE_TEXT` e monta o schema.

O resultado é que a garantia do critério 3 fica inteiramente por conta da obediência do modelo:
se o Claude ignorar o bloco `MANDATORY RIG` em uma das cenas, o `script.json` é gravado como
`done`, sem nota nenhuma no `log` do job, e a UI apresenta um prompt fora do preset anunciado no
cabeçalho ("preset documentary-street").

O que mascara o buraco é o formato do fake: em `tests/test_storyboard_api.py:625` o fake extrai
o rig do prompt enviado (`re.search(r"MANDATORY RIG, IDENTICAL IN EVERY SCENE: (.+?) — write", ...)`)
e o devolve dentro do `image_prompt`. Por isso
`test_script_carries_the_preset_rig_into_every_scene` (T2.3) sempre passa — ele prova o caminho
prompt→eco do fake, não uma regra do servidor. Nenhum teste cobre "modelo devolveu cena sem o
rig". A metade de baixo (o rig ir no prompt) está bem coberta por T1.2.

Sugestão: com `preset` não nulo, verificar em `_parse_script` (ou em `_script_payload`, que já é
o ponto onde o serviço normaliza) se `REALISM_PRESETS[preset]["rig"]["camera"]` /`["lens"]`
/`["format"]` aparecem no `image_prompt` de cada cena e, quando não aparecerem, registrar a cena
no `log` do job (ou marcar o job em erro, se a leitura do FDD for a estrita — a §6 já define
"resposta inválida = job em erro, nunca completar com conteúdo inventado"). Acrescentar um teste
com fake que devolve uma cena sem o rig para congelar o comportamento escolhido.

## Triage

- Decision: `ACCEPTED`
- Notes:

**Válida.** Causa raiz: a metade de baixo do critério 3 `[cross-feature]` não existia. O prompter
manda o bloco `MANDATORY RIG` (metade de cima, coberta por T1.2), mas nem `prompter._parse_script`
nem `sb._script_payload` conferiam o retorno. O `test_script_carries_the_preset_rig_into_every_scene`
(T2.3) media o eco do fake, não uma regra do servidor: com o modelo desobediente, o `script.json`
era gravado `done` com prompt fora do preset anunciado no cabeçalho.

**Decisão de projeto (leitura ESTRITA do FDD §6):** rig ausente em qualquer cena invalida a
resposta INTEIRA e o job vai a `state: "error"` — nada de anotar no `log` e gravar assim mesmo,
porque "resposta inválida → job em erro, nunca completar com conteúdo inventado". Regerar não custa
crédito (Claude CLI é assinatura local, ADR-025), então a rigidez transforma o critério 3 em
invariante em vez de esperança na obediência do modelo.

**Correção aplicada** (`studio/storyboard/service.py`, sem tocar no prompter):

- novo `_require_preset_rig(scenes, preset)`: com `preset` não nulo, exige que
  `prompter.REALISM_PRESETS[preset]["rig"]["camera"] / ["lens"] / ["format"]` apareçam LITERALMENTE
  (comparação exata, sensível a caixa — é o que "literalmente" quer dizer) no `image_prompt` de
  CADA cena. Falhando, levanta `RuntimeError` citando quais cenas e quais partes do rig faltaram:
  `roteiro fora do rig do preset documentary-street: cena 2 sem camera ("Blackmagic Pocket 6K Pro"),
  lens ("Cooke S4"), format ("Super 35") — nada foi gravado, gere de novo`. Com `preset=None` não há
  rig a cobrar e a função sai na primeira linha;
- a chamada é a PRIMEIRA linha de `_script_payload` (ponto sugerido pela issue): é o funil único por
  onde a resposta do prompter vira arquivo, então nenhum payload chega ao disco sem passar por ela.
  Como a validação roda antes do `mkdir`/`write_json_atomic`, o `script.json` anterior fica intacto.
  O `RuntimeError` é capturado pelo `except` do `run(job)` (ver issue_003), que emite a linha
  `script_job` de erro e a linha `roteiro falhou: ...` no `log` do job antes do `raise`.

**Testes acrescentados** (`tests/test_storyboard_api.py`), com o fake ganhando o parâmetro
`sem_rig=(...)` — a lista de cenas em que o bot DESOBEDECE:

- `test_script_scene_without_the_preset_rig_is_an_error`: gera um roteiro válido, guarda os bytes,
  roda de novo com a cena 2 sem rig e cobra `state == "error"`, a mensagem citando `cena 2 sem` +
  cada uma das três chaves do rig com o valor esperado, a AUSÊNCIA de `cena 1 sem`/`cena 3 sem`
  (a mensagem aponta a cena certa), a linha `roteiro falhou` no `log` e o `script.json` anterior
  byte a byte igual;
- `test_script_without_preset_does_not_demand_any_rig`: com `preset: null` e as duas cenas sem rig,
  o job termina `done` — a cobrança é exclusiva do caminho com preset.

Mutante conferido: comentando a chamada a `_require_preset_rig`, o teste novo falha
(`error != done`), então o teste mede a regra do serviço, não o eco do fake.

**Arquivo fora do escopo original tocado, com motivo:** `tests/test_storyboard_service.py`. O fake
de nível serviço (`_script_result`/`_fake_prompter_script`) devolvia `image_prompt` sem rig
enquanto o preset default (`documentary-street`) continuava valendo — com a validação nova, cinco
testes preexistentes (T2.18 a T2.22) passaram a cair em `error`. Eles não medem rig nenhum, então
a correção foi mínima e no FAKE, não na regra: o bot passou a ser obediente (recebe o `preset` e
devolve corpo/lente/formato do catálogo dentro de cada `image_prompt`), preservando exatamente o
que cada teste já protegia. Nenhuma asserção desses cinco testes foi alterada.
