# prompter-presets-realismo — fluxo de geração com preset e resolução de default

Diagramas da feature `prompter-presets-realismo` (Wave 9, `[extensão]`), fonte normativa
`docs/domains/studio/features/prompter-presets-realismo-fdd.md` — em especial a seção 0
(amendas do gate W3), que vence sobre o restante do FDD. Conferidos contra a implementação em
`studio/common/prompter.py`, `studio/common/settings.py`, `studio/creditos/router.py`,
`studio/etapas/base/router.py` e `studio/base/service.py`.

## 1. Fluxo principal de geração com preset (etapa 3 · base)

A tela da etapa 3 carrega o catálogo em `GET /api/prompter/presets` (rota hospedada em
`studio/creditos/router.py`) e monta o `<select>` `#baseRealismPreset`, sempre com a opção
`(sem preset)` na frente. No "Gerar prompt", o `view.js` manda o campo aditivo `preset` no body do
`POST /api/projects/{pid}/base/prompts/generate`: id escolhido ou `null`. O router valida o id
contra `REALISM_PRESETS` no `field_validator` do `PromptGenReq` — id desconhecido vira **HTTP 422
antes** de o endpoint rodar, isto é, antes de qualquer chamada ao Claude CLI. Quando o campo vem
**ausente** do payload (clientes de API; a tela sempre envia o campo), o sentinela
`settings.PRESET_UNSET` atravessa o router e quem resolve o default é o serviço, via
`settings.resolve_preset("base", pid, preset)` → `preset_default_for` (projeto → global → código).
O `prompter` só injeta `preset_block` quando o preset resolvido não é `None`; sem preset o texto
enviado ao CLI é byte-idêntico ao de antes da extensão. A resposta e o histórico
(`prompts.json`) sempre carregam a chave `"preset"`, inclusive com o valor `null`.

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant UI as etapas/base/view.js
  participant CR as creditos/router.py
  participant R as etapas/base/router.py
  participant S as common/settings.py
  participant SV as base/service.py
  participant P as common/prompter.py
  participant CLI as Claude CLI

  UI->>CR: GET /api/prompter/presets?pid=...
  activate CR
  CR->>S: preset_default_for(kind, pid) para cada chave de PRESET_ACTIONS
  S-->>CR: defaults {kind: {preset, source}}
  CR-->>UI: 200 {presets: catálogo REALISM_PRESETS, defaults}
  deactivate CR
  Note over UI: monta o select com "(sem preset)" + os 5 presets<br/>e pré-seleciona o default RESOLVIDO da ação "base"

  U->>UI: escolhe um preset OU mantém "(sem preset)"
  UI->>R: POST /api/projects/{pid}/base/prompts/generate<br/>{..., "preset": "id-do-preset" | null}
  activate R
  Note right of R: o body tem TRÊS estados: ausente = resolver default,<br/>null = sem preset, "id-do-preset" = usar esse

  alt id fora de REALISM_PRESETS
    R-->>UI: 422 preset desconhecido (lista de ids válidos)<br/>validação no field_validator, antes de chamar o serviço/CLI
  else preset válido, null ou campo ausente
    R->>SV: generate_prompt(pid, ..., preset=req.preset_arg())
    activate SV
    opt campo "preset" ausente do payload (PRESET_UNSET)
      SV->>S: resolve_preset("base", pid, PRESET_UNSET)
      S->>S: preset_default_for: projeto → global → código
      S-->>SV: (resolvido, explícito=None)
    end
    SV->>P: from_images("base", ..., preset=preset resolvido)
    activate P
    alt preset resolvido não é None
      P->>P: role + preset_block(preset) + OUTPUT_SPEC<br/>negativos do preset mesclados no campo "negative"
    else preset resolvido é None (opt-in)
      P->>P: role intocado — prompt byte-idêntico ao de hoje
    end
    P->>CLI: prompt do papel (+ imagens)
    CLI-->>P: JSON do bot
    P-->>SV: {prompt, negative, camera, notes_pt, source, seconds, "preset"}
    deactivate P
    SV->>SV: grava a entrada em prompts.json com "preset"
    SV-->>R: resultado + provenance
    deactivate SV
    R-->>UI: 200 resposta atual + "preset": id usado ou null
  end
  deactivate R
```

## 2. Resolução do preset default por ação (projeto → global → código)

`settings.preset_default_for(kind, pid)` resolve o preset default de uma **ação** registrada em
`settings.PRESET_ACTIONS` — registro aberto, inicializado com `{"mood": None, "base": None,
"motion": None}` e extensível por outros módulos em import time (a feature consumidora
`storyboard-roteiro-llm`, da sub-wave 2, acrescenta a chave pontuada `storyboard.script` com
default `documentary-street`; ela não é entregue por esta frente). A cadeia é projeto → global →
código e tem três desfechos que importam: um `null` **persistido** encerra a cadeia naquele nível
(opt-out deliberado, `source` é aquele nível); uma chave **ausente** cai para o próximo nível; e um
id configurado que **saiu do catálogo** `REALISM_PRESETS` é ignorado como se ausente, também caindo
para o próximo nível — a UI nunca fica presa a um id morto. O default de código de `mood`, `base` e
`motion` é `null` (gate W3, amendas A1/A2): o comportamento é **opt-in**, sem preset a menos que
alguém configure um override.

```mermaid
flowchart TD
  IN["preset_default_for(kind, pid)"]
  REG{"kind registrado em<br/>settings.PRESET_ACTIONS?"}
  ERR["ValueError → HTTP 422<br/>ação de preset desconhecida"]

  subgraph N1["Nível 1 · override de projeto — config.json do projeto"]
    PRJ{"pid informado e chave<br/>presente em prompter_presets?"}
    PRJN{"valor persistido<br/>é null?"}
    PRJV{"id existe em<br/>REALISM_PRESETS?"}
    OUTP["preset = null · source = project<br/>opt-out deliberado — cadeia encerrada aqui"]
    USEP["preset = id · source = project"]
  end

  subgraph N2["Nível 2 · override global — STATE_DIR/config.json"]
    GLB{"chave presente<br/>em prompter_presets?"}
    GLBN{"valor persistido<br/>é null?"}
    GLBV{"id existe em<br/>REALISM_PRESETS?"}
    OUTG["preset = null · source = global<br/>opt-out deliberado — cadeia encerrada aqui"]
    USEG["preset = id · source = global"]
  end

  subgraph N3["Nível 3 · default de código — PRESET_ACTIONS"]
    COD["valor registrado em PRESET_ACTIONS para o kind"]
    CODV{"é null ou id fora<br/>do catálogo?"}
    OUTC["preset = null · source = code<br/>opt-in: nada é injetado no prompt"]
    USEC["preset = id · source = code<br/>ex.: storyboard.script = documentary-street"]
  end

  IN --> REG
  REG -- "não" --> ERR
  REG -- "sim" --> PRJ

  PRJ -- "chave ausente ou sem pid" --> GLB
  PRJ -- "chave presente" --> PRJN
  PRJN -- "sim" --> OUTP
  PRJN -- "não" --> PRJV
  PRJV -- "sim" --> USEP
  PRJV -- "não · id fora do catálogo → ignorado" --> GLB

  GLB -- "chave ausente" --> COD
  GLB -- "chave presente" --> GLBN
  GLBN -- "sim" --> OUTG
  GLBN -- "não" --> GLBV
  GLBV -- "sim" --> USEG
  GLBV -- "não · id fora do catálogo → ignorado" --> COD

  COD --> CODV
  CODV -- "sim · mood, base e motion são null" --> OUTC
  CODV -- "não" --> USEC

  EXT["Registro extensível: outra feature acrescenta a<br/>própria ação sem editar esta frente<br/>(storyboard-roteiro-llm registra storyboard.script)"] -.-> N3

  RES["Resultado {kind, preset, source}<br/>consumido pelo bloco defaults de GET /api/prompter/presets<br/>e por resolve_preset quando o campo preset vem ausente"]
  OUTP --> RES
  USEP --> RES
  OUTG --> RES
  USEG --> RES
  OUTC --> RES
  USEC --> RES
```

## 3. Notas de divergência FDD × código

- **Pré-seleção da UI.** O FDD §4 diz que a UI "pré-seleciona `documentary-street` como sugestão
  visual". O `studio/etapas/base/view.js` implementado pré-seleciona o default **resolvido**
  (`defaults["base"].preset`), que com o opt-in do gate W3 é `null` — ou seja, a tela abre em
  `(sem preset)`. É o comportamento coerente com as amendas A1/A2 (a seção 0 vence).
- **Campo sempre presente vindo da tela.** A tela envia `preset` em toda requisição (id ou `null`),
  então o caminho "campo ausente → serviço resolve o default" vale na prática para clientes de API;
  a distinção ausente × `null` é sustentada pelo sentinela `settings.PRESET_UNSET`.
- **Validação do id.** O FDD §5 previa `preset_block` levantando `KeyError` convertido em 422 pelo
  router; o código introduziu `prompter.valid_preset` (levanta `ValueError`) usado no
  `field_validator` do body, o que produz o 422 mais cedo, antes do corpo do endpoint.
- **Etapa 2 (mood).** Conforme a amenda A4, o seletor de preset **não** foi entregue na tela da
  etapa 2 (endpoint morto por ADR-014); o campo `preset` no endpoint é aditivo e fica pronto para
  quando a tela existir. Por isso o diagrama 1 usa a etapa 3 (base) como fluxo principal.
