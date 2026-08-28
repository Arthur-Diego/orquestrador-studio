# Wave 5 — Retro (mood mosaico · base compacta · cena multi-keyframe)

**Fechada em:** 2026-08-28 · **Recon:** `../recon-wave-5.md` · **Contrato:** `wave-5.md`

## Resultado

| Frente | Feature | PR | Testes | Observação |
|---|---|---|---|---|
| A | mood-mosaico-base-compacta (pontos 1,2,4) | **#62** (merge em `develop`) | 771 passed | `Studio.ui.moodMosaic`; `/api/moodboards` com `thumbs`; etapa 3 compacta; card da imagem base final |
| B | cena-multi-keyframe (ponto 3) | **#63** (merge em `develop`) | 777 passed (integrado A+B) | `scenes.json` `images[]`/`primary`; **ADR-018** (desvio da aula 010, `[extensão]`) |

Integração em série A → B. Verify integrado (A+B) verde, incluindo `test_animate_api`
(cadeia `scenes.json → storyboard.json → animate` sã). Duas frentes independentes, **zero
sobreposição de arquivos**, rebase de B sobre `develop`+A **limpo**. Nenhuma parada de
HARD-GATE durante a execução.

## Decisões automáticas (regra determinística, sem perguntar)

- Ambas as frentes: **implementação direta** (não SDD/Compozy) e **sem Postman** — trabalho
  pequeno, sem contrato HTTP novo. (Passo 6 do `dd-parallel-feature`.)
- A: grade 2×2 fixa com "+N"; seletor de fonte do mood mantido (só reposicionado, ADR-013);
  reuso de `base/base_final.png` + campo `final` existente (sem rota nova).
- B: `primary` default = primeiro item; migração retrocompatível de `image`→`images`,`primary`.

## Desvio de método (registrado)

- **ADR-018** — cena com galeria de keyframes + uma principal. Contraria a aula 010 (1 keyframe
  por cena); aprovado explicitamente pelo dono do produto; marcado `[extensão]` no código,
  commits e docs; a principal semeia a base dos ângulos (painel 03) e é o hero do `storyboard.md`.

## Divergências e soft-fails (e como foram fechados na W5)

1. **Contrato publicado divergente** (`wave-1.md` e `storyboard-fdd.md` "Provides" ainda com
   `image` singular). A Frente B **corretamente não auto-aceitou** editar artefato compartilhado
   e subiu como pendência `[cross-feature]`. → Reconciliado na W5 pelo orquestrador
   (commit `ADH-OS-20260828-16`): schema atualizado para `images`/`primary` com nota ADR-018.
2. **Soft-fail da Frente A:** bump do HLD (`moodMosaic` no catálogo `Studio.ui`) deixado para a
   integração para não colidir com a Frente B no domínio `studio`. → Aplicado na W5 (mesmo commit).
3. **Teste visual no navegador não executado** nas duas frentes (worktree headless; `make verify`
   roda sem rede/navegador). Cobertura por testes de view/serviço. Não é o frontend-fit, então
   `dd-front-e2e` não se aplica.

## Aprendizados → regras

1. **Evolução de contrato publicado é tarefa da W5, não da frente.** Quando uma frente muda um
   schema/contrato descrito em `wave-N.md` ou no "Provides" de um FDD, a frente registra a
   mudança como pendência `[cross-feature]` (nunca edita o artefato compartilhado na sua
   worktree) e o **orquestrador reconcilia o contrato na integração**. Confirmou a regra do
   HARD-GATE "divergência com contrato publicado nunca é auto-aceita". (Reforço para
   `references/gates.md`.)
2. **Soft-fail de doc compartilhado que a frente não pode tocar** (HLD/catálogo do shell no
   domínio comum) → listar como pendência de W5; o orquestrador aplica no fecho. O invariante
   de não-sobreposição de arquivos entre frentes vale também para docs compartilhados.
   (Reforço para `references/ambiente.md`.)
3. **UI pequena sem contrato HTTP:** decidir implementação direta + sem Postman por regra, não
   perguntar — validou o Passo 6 em mais um caso.
4. **Cobertura visual fica fora do `make verify`.** Para mudanças de tela fora do frontend-fit,
   recomendar conferência visual manual antes do merge (aqui: `#/moodboards`, etapa 2, etapa 3,
   painel 02 do storyboard) — não bloqueia, mas fica anotado como risco residual.

## Pendências que seguem (fora do escopo da wave)

- Migração de `studio/storyboard/angles.py` para `studio/common/multishot.py` (antecipada pela
  ADR-017) segue pendente — registrada na ADR-018 como fora de escopo desta reescrita.
- Worktree antiga `feature-adh-os-20260827-13-storyboard` (sessão anterior) continua no
  workspace → candidata ao `dd-parallel-clean`.
- Promoção `develop → main` (as duas features seguem o gitflow: só concluídas após merge em
  `main`, por PR de promoção).
