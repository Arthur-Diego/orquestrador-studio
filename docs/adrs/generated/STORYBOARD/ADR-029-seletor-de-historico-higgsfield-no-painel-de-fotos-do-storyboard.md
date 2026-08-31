# ADR-029: Seletor de histórico Higgsfield no painel de fotos do storyboard

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STORYBOARD
**Task-Id:** ADH-OS-20260831-15
**ADRs relacionados:** [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](../STUDIO/ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-016](../STUDIO/ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md)

## Contexto e Problema

O painel de fotos do storyboard (etapa 4) importa as gerações que o usuário fez na Higgsfield por
três caminhos: upload, pasta Downloads e **histórico do CLI** (`higgsfield generate list`). O botão
"Importar do histórico Higgsfield" era **cego**: chamava `POST .../import/history` com `{size: 50}`
e o serviço baixava e ingeria **todas** as URLs de **todos** os jobs retornados.

Isso tem dois problemas de uso:

1. **Sem pré-visualização.** O usuário não vê o que vai entrar — importa o histórico inteiro e só
   depois descobre o que veio (inclusive gerações antigas ou de outra campanha).
2. **Sem escolha.** Não há como trazer só as 2–3 fotos que interessam para aquela cena; é tudo ou
   nada, e a limpeza depois é manual (apagar candidatas uma a uma).

O card pede o **painel de fotos geradas com seletor** para visualizar o histórico Higgsfield e
escolher quais importar, respeitando ADR-002 (via CLI oficial, nunca scraping da UI).

## Decisão

Separar **listar** de **importar**, com uma `key` estável por mídia amarrando a escolha da UI ao
download:

1. **Camada de ingestão (`studio/common/ingest.py`)** — genérica, reaproveitável por outras etapas:
   - `history_preview(kind, size, prompt_filter)` chama `hf.history_media` e devolve
     `{items: [{key, url, prompt, model, created, job_id}], jobs}` **sem baixar nada**.
   - `_media_key(url)` = SHA-1 curto da URL **sem query** (o link assinado muda a cada listagem, o
     caminho do arquivo não). É a chave estável que o seletor devolve.
   - `import_history(..., keys=None)` ganha o parâmetro `keys`: quando presente, baixa/ingere só as
     mídias cuja `key` está no conjunto; `None`/vazio mantém o comportamento antigo (tudo).

2. **Serviço do storyboard (`studio/storyboard/service.py`)**: `preview_history(pid, ...)` e o
   `import_history(pid, ..., keys=None)` como wrappers finos sobre a camada de ingestão.

3. **Rotas (`studio/etapas/storyboard/router.py`)**:
   - Nova `GET .../storyboard/history/preview` — lista para o seletor. Exige CLI instalado + login
     (é o próprio `higgsfield generate list`), mesmo gate 409 da importação; erro do CLI → 502.
   - `POST .../storyboard/import/history` aceita `keys` opcional em `HistoryReq`.

4. **Frontend (`studio/etapas/storyboard/view.js`)**: o botão "Importar do histórico Higgsfield"
   abre um **modal-seletor** — grade de miniaturas com legenda do prompt, clique marca/desmarca
   (padrão `.card.sel` reaproveitado do multiselect de refs), "Selecionar tudo" e "Importar
   escolhidas". Só as marcadas entram no storyboard.

## Restrições respeitadas

- **Ponte só via CLI (ADR-002):** tanto o preview quanto a importação usam
  `hf.history_media` (`higgsfield generate list`). Nenhuma chamada a `api.higgsfield.ai` nem
  scraping da UI. As miniaturas do seletor apontam para as próprias URLs assinadas que o CLI
  devolve.
- **`#sbPreset` e fórmulas da aula intocados (ADR-004):** este trabalho é só ingestão/UI de import;
  não toca em prompts, presets nem geração.
- **Núcleo intocado, só plugin+serviço (ADR-010):** mudanças ficam na etapa storyboard e na camada
  comum de ingestão.
- **Livro-caixa (ADR-016):** importar histórico não gera crédito (é download de mídia já criada),
  então não há `record_generation` — coerente com o comportamento anterior.

## Consequências

- O painel deixa de importar o histórico às cegas: o usuário vê e escolhe. O caminho antigo
  (importar tudo) continua acessível por "Selecionar tudo" → "Importar escolhidas".
- **Contrato novo (aditivo):** `GET .../storyboard/history/preview` e o campo `keys` em
  `HistoryReq`. Chamadas antigas sem `keys` mantêm o comportamento de importar tudo.
- Regressão coberta por `test_history_preview_lists_without_downloading` (lista com `key` estável e
  **não** baixa nada) e `test_history_import_only_selected_keys` (importa só a mídia escolhida). O
  teste `test_history_import_needs_cli_and_maps_failures` (importar tudo) segue verde.
- **Escopo entregue:** só o seletor do storyboard (enxuto). Sugestões para uma wave futura, fora
  deste PR: (a) replicar o mesmo seletor em base e mood, que hoje também importam histórico às
  cegas; (b) um painel agregado cross-etapa consolidando as fotos geradas num só lugar.
