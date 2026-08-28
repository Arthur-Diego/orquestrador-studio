### FDD: base-painel01 — referência grande sem espaço morto + copiar/gerar-via-CLI no prompt [extensão]

**Wave 6 · Frente D · Branch:** `feature/adh-os-20260828-22-base-painel01`
**Recon:** `docs/domains/studio/recon-wave-6.md` (§FRENTE D). `[extensão]`/visual + reuso (sem ADR).
Arquivos: `studio/etapas/base/view.{html,js}`, `studio/base/service.py` (só se necessário), testes.
**CSS novo só no `<style>` escopado `.bs-` de `base/view.html`** — **não tocar `style.css`/`ui.css`.**

### 1. Painel 01: referência grande, fim do espaço morto (`base/view.html` + `view.js`)
- Hoje `.refpick` usa `#refGallery.gallery.xs` (thumbs 120px, capado 560px, `style.css:407`): com
  1 referência o thumb fica pequeno e sobra uma faixa vazia à direita (recon §D.1).
- Redesenhar o painel 01 com layout escopado `.bs-`: **preview grande da referência selecionada**
  (ocupa a largura útil do painel, `object-fit:cover`, altura confortável) + uma **tira compacta**
  das demais referências para trocar a seleção (mantém `#refGallery`/`renderRefGallery` como a tira
  pequena; adiciona `#baseRefHero` com a selecionada em tamanho grande). A junção mood×ref
  (`#baseJunction`) e o prompt seguem abaixo. Resultado: sem faixa morta, referência legível.
- Não mudar a lógica de seleção (`selectRef`, `view.js:139-143`) — só a apresentação.

### 2. Prompt do painel 01: copiar (já existe) + gerar via CLI (reuso do painel 03)
- **Copiar** já existe no card do prompt (`promptCard` + handler `view.js:455-461`) — manter e
  garantir visível.
- Adicionar, junto do prompt do painel 01, um botão **"Gerar via CLI"** que reusa o fluxo do
  painel 03 (`gerarViaCli`/`genBody`, `view.js:408-440`) **forçando `kind:"situation"**"
  (independentemente do stepper): custo (`/base/cost`) → `ui.confirmCost` → `ui.progressJob`
  (`/base/generate`, `/base/job`), como o botão `#btnBaseCli` existente. Após gerar, mostra o
  resultado/atualiza as candidatas (reusar `showResult`/`load`).
- Auto-aceite: o botão do painel 01 age sempre sobre a situação (o prompt do painel 01 é o da
  situação); não interfere no stepper do painel 03.

### 3. Testes
- Contrato de view (DOM) do painel 01: presença do hero da referência e do botão "Gerar via CLI"
  no painel 01. Não quebrar os testes existentes de estrutura da etapa 3 (foram atualizados na
  wave 5 para os 3 painéis + junção).
- Se a geração via CLI no painel 01 usar as mesmas rotas, cobrir o `genBody` com `kind:"situation"`.

### 4. Verificação
`make verify` verde. Manual: painel 01 com a referência grande e sem espaço morto; prompt com
"Copiar" e "Gerar via CLI" funcionando.

### 5. Fora de escopo
Frentes A/B/C. Não alterar o painel 03 nem o stepper.
