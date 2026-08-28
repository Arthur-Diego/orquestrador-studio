### FDD: higgsfield-min-dedup — não duplicar candidatas com o companion `_min.webp`

**Wave 6 · Frente A · Branch:** `feature/adh-os-20260828-19-higgsfield-min-dedup`
**Recon:** `docs/domains/studio/recon-wave-6.md` (§FRENTE A). Bugfix puro (sem ADR).

### 0. Bug (verificado no board real `moodboards/teste-mood`)
Cada geração devolve a imagem cheia `X.png` **e** um preview `X_min.webp`. `higgsfield.generate`
(`studio/higgsfield.py:153`) coleta TODA URL de mídia (`MEDIA_URL_RE`) e só deduplica URL idêntica
→ ingere as duas → 2 candidatas por resultado (usuário pediu 4, board ficou com 8: 4 pares
`.png`+`_min.webp`). O mesmo padrão em `history_media` (`:110`).

### 1. Correção (na fonte, `studio/higgsfield.py`)
- Novo helper `_dedup_min(urls: list[str]) -> list[str]`: agrupa por **basename normalizado**
  (remove o sufixo `_min` antes da extensão e ignora a extensão) e, por grupo, mantém **uma** URL,
  preferindo a **não-`_min`** (a cheia) quando existir; se só houver a `_min`, mantém-a. Preserva a
  ordem de aparição.
- Aplicar em `generate` (linha 153, sobre o resultado de `MEDIA_URL_RE.findall`) e em
  `history_media` (linha 110). Contrato `{raw, urls, id}` inalterado — só reduz duplicatas.
- Não tocar os 5 consumidores (`common/multishot.py`, `storyboard/angles.py`, `base/service.py`,
  `mood/service.py`, `common/ingest.py`); `animate` já é imune.

### 2. Testes (`tests/test_higgsfield_bridge.py`)
- Payload fake com `["…/a.png","…/a_min.webp","…/b.png","…/b_min.webp"]` → `generate` devolve só
  `[a.png, b.png]`.
- Só `_min` presente (`c_min.webp` sem `c.png`) → mantém `c_min.webp`.
- Sem par (`d.png` sozinho) → intacto. Mesma cobertura para `history_media`/`import_history`.

### 3. Verificação
`make verify` verde. Sem mudança de contrato público.

### 4. Fora de escopo
Limpeza dos 4 duplicados `_min` já cadastrados em `teste-mood` (dado local não versionado — o
orquestrador limpa na integração).
