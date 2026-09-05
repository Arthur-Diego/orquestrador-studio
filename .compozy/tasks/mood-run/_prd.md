# PRD: a tela de mood boards dispara a cadeia de skills `mood_` (Wave 10 · sub-wave B)

Task-Id `ADH-OS-20260902-01` · Card <https://trello.com/c/kP0XTHNC> · Domínio `mood`
(área global da biblioteca de mood boards, ADR-013).

Plano de origem: `docs/domains/mood/planos/plano-01-tela-chama-orquestrador.md`.
Terreno da wave: `docs/domains/mood/recon-wave-10.md`.

Spec normativa completa: `_techspec.md` (o FDD, aprovado no gate em lote da W3).
**Em qualquer divergência, `_techspec.md` vence.**

## Problema

A cadeia `mood_` (vibe → DNA visual → prancha) só roda na mão, num terminal, com o operador
respondendo às três paradas humanas. O resultado cai em `processo_manual/moodboard/`, que nenhuma
tela lê: quem quer a prancha dentro do Studio copia arquivos à mão. O trabalho de direção de arte
fica fora da ferramenta que deveria executá-lo.

## Quem sofre

O operador do Studio — a mesma pessoa que já monta mood boards na tela. Ela hoje alterna entre
terminal e navegador e reconcilia duas árvores de arquivo na cabeça.

## Como contornam hoje

Rodam `/mood_orquestrador` no terminal, esperam ~15 minutos sem retorno de progresso, e depois
copiam `_moodboard.jpg` para dentro da pasta do board na mão.

## Resultado esperado

Um painel na tela do mood board que:

1. mostra os objetivos disponíveis e os defaults sem nenhum valor escrito à mão na tela;
2. mostra **a conta de downloads antes de confirmar** — a corrida baixa dezenas de imagens de
   terceiros e é irreversível em tempo e em disco;
3. dispara a corrida como job assíncrono com progresso honesto;
4. devolve as pranchas na própria tela, com `leitura.md` e `curadoria.md` acessíveis — a revisão
   humana que o modo automático deslocou para depois.

## Restrições conhecidas

- **Nunca gerar imagem com IA nem gastar crédito Higgsfield.** Proibição explícita do dono do
  produto e HARD-GATE das próprias skills. A cadeia `mood_` é gratuita: nenhum `spend_action`
  (ADR-016), nenhum `require_cli()` de Higgsfield (ADR-002).
- **Nunca chave de API.** A ponte com o modelo é o Claude CLI local, com a assinatura do usuário,
  como já faz `studio/common/prompter.py`.
- **`studio/web/*` é núcleo (ADR-010).** Esta frente NÃO edita `studio/web/moodboards.js`; o front
  sai como patch em `docs/domains/mood/features/pendencias/`. Ver seção 3.1 do `_techspec.md` —
  é a restrição que derrubou as duas frentes anteriores da wave.
- **Não editar** `studio/app.py`, `studio/steps.py`, `studio/config.py`, `studio/higgsfield.py`,
  `studio/etapas/__init__.py`, `studio/etapas/mood/view.*`, `studio/common/prompter.py`.
- **Não afrouxar** `tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo`,
  sob nenhuma justificativa. Quem achar que precisa, para e reporta.
- Testes sem rede e sem `claude` real (ADR-008): fake do CLI por monkeypatch de
  `skill_runner.BIN` e `skill_runner.subprocess.run`.
- Estado em arquivo, sem banco (ADR-003); job em thread com polling (ADR-006).

## Critérios de sucesso do produto

- Com `claude` ausente do PATH, a tela mostra "sem claude" e o botão fica desabilitado; nada quebra.
- Um board + 1 objetivo produz `_moodboard.jpg` visível na tela sem passo manual.
- `todos --board 8 --n 3` estima **84** downloads antes de qualquer download acontecer.
- Segundo disparo enquanto roda devolve 409.
- As imagens baixadas não podem entrar no git.
- `make verify` verde (exceto as 3 falhas de baseline conhecidas da máquina, listadas na
  seção 9 do `_techspec.md`).
