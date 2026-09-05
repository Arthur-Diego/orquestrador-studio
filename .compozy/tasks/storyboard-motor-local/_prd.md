# PRD — Motor de imagem local no Storyboard `[extensão]`

- **Task-Id**: ADH-OS-20260905-01
- **Domínio**: storyboard (etapa 4)
- **Status**: aprovado (aprovação total do usuário — modo auto-aceite)

## 1. Problema observado
Na etapa 4, toda geração de imagem custa crédito da Higgsfield, inclusive iterar em keyframes e
"consertar" um detalhe. O "inpaint" atual (`edit_area`) é uma aproximação: manda a foto rabiscada
ao modelo pago e pede por texto para mudar só na região — sem máscara real, às vezes muda fora da
área e gasta crédito a cada tentativa (`service.py`: *"aproximação best-effort, nunca inpaint real"*).

## 2. Quem sofre
O orquestrador (usuário da ferramenta) que precisa gerar muitas variações e fazer ajustes
localizados finos antes de animar — o custo e a imprecisão travam a iteração.

## 3. Como contornam hoje
Geram tudo pago na Higgsfield, ou saem da ferramenta e usam a skill `kling-storyboard-video`
(ComfyUI/Flux local) por fora, perdendo a integração com o projeto/candidatos do studio.

## 4. Resultado esperado
Na mesma tela do Storyboard, um caminho **local e grátis** ADICIONAL (sem tirar a Higgsfield):
1. **Gerar keyframes localmente** (Flux via `engine`) — grátis, para iterar à vontade.
2. **Inpaint REAL por máscara** num modal/tela de edição do próprio sistema: o usuário pinta a
   máscara, escreve a instrução, roda local (grátis), vê antes/depois e itera sobre o resultado —
   sem nunca abrir a UI do ComfyUI. A região fora da máscara é preservada de verdade.
O resultado entra como candidato normal e segue o fluxo (seleção → cena → ângulos → animate).

## 5. Restrições conhecidas (do recon/ADRs)
- **Higgsfield permanece** — motor local é opção adicional, nunca substituto (decisão do usuário).
- Núcleo intocável (ADR-010/032): novo módulo `studio/localengine.py` + UI co-localizada.
- ComfyUI/`engine` é serviço externo local (como o CLI da Higgsfield já é) — precisa de gate de
  saúde (409 quando offline) e de ser fakeável nos testes (sem rede/navegador).
- Local é grátis → sem cost-confirm e sem débito no livro-caixa.
- Tudo `[extensão]` + ADR novo (supera parcialmente ADR-004: agora existe inpaint real).

## 6. Fora de escopo
- Substituir a Higgsfield ou o `edit_area` legado (ambos ficam).
- Animação (etapa 5 já faz Kling; alternativa local LTX-Video fica como sugestão futura).
- Upscale local (a etapa já tem upscale pago nos ângulos).

## 7. Valor
Iteração ilimitada e grátis + ajuste localizado preciso, integrados ao fluxo, sem retrabalho fora
da ferramenta e sem gasto de crédito na exploração.
