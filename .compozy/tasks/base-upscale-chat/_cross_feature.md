# Pendências `[cross-feature]` — base-upscale-chat (Wave 11 · F11)

Task-Id: `ADH-OS-20260906-13` · Card #94 · Branch `feature/adh-os-20260906-13-base-upscale-chat`
Registrado pela **task_07** (Build Order passo 9). Fonte: `_techspec.md` §9 critérios **18** e **19**,
§8 "Fronteira mockada", §11 passo 9.

## Por que ficam pendentes

Esta worktree é uma frente isolada da sub-wave 2. Os critérios 18 e 19 só se observam no **estado
integrado**, porque dependem de duas frentes que não estão nesta branch:

- **F03 `chat-sync`** (card #87) — publica `state_changed` e `frontend/src/shell/events.ts`, sem os
  quais a tela Base aberta não recarrega sozinha depois do clique no chat.
- **F04 `mcp-pick-shape`** — corrige `_images_for` (URL duplicada no fallback) e fixa o formato do
  sufixo JSON que `_result_json` emite.

Conforme §8, esta frente implementou contra o contrato dessas duas e **não** força evidência local
com navegador (sem rede, sem browser, sem ComfyUI, sem `make qa-*`). A ordem de integração da
sub-wave 2 é **F10 → F08 → F11 → F09**; a reconfirmação acontece na **W5**.

---

## Critério 18 — upscale pelo chat chega na tela Base sem F5

> No estado integrado: upscale disparado pelo chat → a imagem nova aparece no chat com antes/depois →
> clique em "Usar como imagem base" → a tela Base (já aberta, **sem navegação e sem F5**) mostra
> `base/base_final.png` atualizada e o badge "upscale 2x ✓" na grade.

**Status:** pendente · evidência = gravação ou sequência de prints na PR da frente + reconfirmação na W5.

### Roteiro de evidência (executar com a stack integrada de pé)

Pré-condição: campanha com etapa 3 já tendo uma candidata de `situation` (e, idealmente, `label`),
para que o upscale tenha origem e o par antes/depois não caia no fallback.

| # | Ação | O que o print/gravação precisa mostrar |
| --- | --- | --- |
| 1 | Abrir a campanha e **deixar a tela Base aberta** no painel 03 (cadeia). | A tela Base visível **antes** de qualquer ação no chat — é ela que não pode ser recarregada à mão. |
| 2 | No dock do chat, pedir o upscale (o agente encadeia `base_generate` + `job_wait` + `base_review`). | O `ui.show` do job e, na sequência, **um único** `ask` de `choose_images`. |
| 3 | Conferir o card do ask. | Para cada candidata nova, o par **antes/depois** lado a lado. A legenda do "depois" é `depois · upscale` (`KINDS`), não "upscale 2x". |
| 4 | Clicar na imagem (não no botão). | Abre o **lightbox** (`Modal` do design system) e **não** responde o ask — o ask continua aberto atrás. |
| 5 | Fechar o lightbox e clicar em **"Usar como imagem base"**. | O botão da ação vinda de `actions` (`studio/mcp/actions.py:388`). Não confundir com o botão homônimo da própria tela Base (`index.tsx:1007`). |
| 6 | **Sem navegar e sem F5**, olhar a tela Base. | `#baseFinalCard` mostrando `base/base_final.png` atualizada (a imagem do upscale) e o stepper `#baseChain [data-step=upscale]` com o rótulo **"upscale 2x"** marcado ✓. |
| 7 | Conferir o retorno do agente no chat. | Última linha com o sufixo `{"selected": ["<id>"], "next_step": "storyboard"}`. |

Passo 6 é o coração do critério: se a tela só atualizar depois de um F5, o que falhou é a ponte
`state_changed` (F03), não esta frente.

**Contraprova a registrar junto:** repetir do passo 2 e responder **"Manter a atual"**. A tela Base
não pode mudar e **nenhum** `POST /base/select` pode sair (critério 7, já coberto localmente por
`tests/test_mcp_actions.py`).

### O que já está provado localmente (não precisa de print)

- Critérios 1–14 e 17, verdes na suíte desta branch.
- Critério 12 (`studio/etapas/base/ui/index.test.tsx`): a tela recarrega com `useStudioChange("base")`
  filtrando por `pid` e com debounce de 400 ms — o **mecanismo** do passo 6 está testado contra o
  contrato de F03; o que falta é vê-lo ligado ao evento real.
- Critério 13: o "antes" do par sai de `source_id` (`originDe`), com fallback `originFor`.

---

## Critério 19 — mesmo sufixo JSON que `base_pick` e `_images_for` sem URL duplicada

> `base_review` e `base_pick` devolvem o mesmo formato de sufixo JSON definido por F04, e
> `_images_for` corrigido por F04 serve o caminho de fallback sem URL duplicada.

**Status:** pendente de confirmação no integrado (após F10 → F08 → F11).

### Metade já garantida nesta branch (por construção)

Ambos os caminhos chamam **o mesmo helper**, então não há como divergirem de formato:

- `base_review` → `studio/mcp/actions.py:415` — `_result_json([cid], _next_step(client, pid))`
- caminho genérico dos `*_pick` → `studio/mcp/actions.py:166` — `_result_json(ids, _next_step(client, pid))`

`_result_json` (`actions.py:94`) é a única fonte do sufixo: sempre a última linha, sempre
`{"selected": [...], "next_step": ...}` com `separators=(", ", ": ")`. Por decisão auto-aceita 11, o
`base_review` só emite o sufixo **quando houve seleção** — `keep:true`, `answered:false` e `no_ui:true`
não emitem, o que é o comportamento correto e não uma divergência de formato.

### O que confere na integração

1. **Paridade de sufixo:** rodar `base_review` e `base_pick` na mesma campanha e comparar a última
   linha das duas respostas — mesmas chaves, mesma ordem, mesmo espaçamento. Um diff de duas linhas
   basta como evidência.
2. **`_images_for` sem URL duplicada:** exercitar o **fallback** de `base_review` (o ramo sem
   candidatas novas, que lista as candidatas já existentes da etapa) e conferir que cada `thumb` do
   payload do ask é servível e aparece **uma única vez** — nada como
   `/files/{pid}/base/files/{pid}/base/…`. `_images_for` (`actions.py:70`) monta a URL por
   `_media_url(f"/files/{pid}", step, thumb)`; a correção de F04 mora aí, então a checagem é sobre o
   código **integrado**, não sobre o desta branch.
3. Registrar o resultado dos dois itens no PR da W5.

---

## Fechamento

- Nada aqui bloqueia o merge desta frente: são critérios de **integração**, por desenho (§8).
- Se qualquer um dos dois falhar na W5, o dono é a frente que integrou por último naquele ponto —
  abrir card próprio em vez de reabrir o #94, salvo se a causa for código desta branch.
- A execução real do cenário de QA `scripts/qa/cenarios/base.py` também fica para a W5 /
  `qa-studio` (critério 16 foi verificado aqui por **diff + leitura estática**: o cenário não foi
  editado e nenhum id/classe que ele usa foi renomeado).
