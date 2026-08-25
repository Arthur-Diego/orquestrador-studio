# Orquestrador Studio

Ferramenta local para executar, **etapa por etapa e sem desviar do roteiro**, o método de
produção de vídeo com IA do curso *"O Orquestrador — Iniciante"* (ABRAhub): referências →
mood board → imagem base → storyboard → ângulos → animação → trilha → montagem → export →
publicação → prospecção. Backend FastAPI + frontend estático; sem build, sem banco.

**Estado (2026-08-25):** as **11 etapas** do curso estão implementadas como plugins (wave 1 do
`/dd-parallel`, 385 testes). Geração de imagem/vídeo continua em "modo UI" (você gera na
interface da Higgsfield e importa) ou via CLI logado. Plano completo em `docs/plano/`.

## Requisitos

- Python 3.12+, Node 18+ (só para o CLI da Higgsfield), Chromium do Playwright.
- Conta Higgsfield (etapa 2 em diante). O CLI oficial: `npm i -g @higgsfield/cli` e
  `higgsfield auth login`.
- WSL2 com WSLg (ou Linux com display) para o login com janela no Pinterest — opcional.

## Instalação e uso

```bash
make setup        # venv + dependências (dev incluído)
make hooks        # hooks de commit (trailer Task-Id)
make run          # http://127.0.0.1:8765
make verify       # ruff + pytest
```

Se não houver Chromium em `~/.cache/ms-playwright`: `. .venv/bin/activate && playwright install chromium`.

## Etapas

### 1 · Referências (aula 009)
Crie um projeto (nome, produto; a **vibe é opcional** — a aula 009 encontra a vibe na etapa 2). "Sugerir termos" → "Buscar e baixar": o scraper
Playwright percorre o Pinterest em ritmo humano com a sua sessão (login opcional; perfil em
`~/.orquestrador-studio/pinterest-profile`), baixa as imagens em maior resolução para
`projects/<id>/refs/candidates/` e você marca as que gosta. "Salvar seleção" copia para
`refs/brainstorming/` e registra origem em `refs/README.md`.
Aviso: automatizar o Pinterest contraria os termos dele — use uma conta secundária. As
imagens são só referência de mood; nunca entram no vídeo final.

### 2 · Mood board (aula 009)
**Uma vibe só.** Primeiro você **acha a vibe**: traz 1–4 imagens cujo sentimento gosta (Pinterest,
Explore do Midjourney, frame de filme). Depois o "bot" da aula — reproduzido com o **Claude CLI**
local (`studio/common/prompter.py`) — escreve **um prompt de vibe** profissional (câmera, lente,
luz, negativos) em dois modos: a partir das imagens + sua instrução, ou só do brief (propósito,
tom, referência estética); há um template fixo sem Claude como fallback. Ambiente, luz e cor — sem
produto, sem pessoas; você gera um grid de 4 na interface da
Higgsfield (onde o ilimitado do plano vale) ou via CLI (gasta créditos); "Nova variação"
troca só a estilização, como ajustar o *Stylization* e regerar. Importe por arrastar,
pela pasta **Downloads do Windows** ou pelo **histórico do CLI**; escolha até 8 imagens no
mesmo mood → `mood/selected/`, `mood/palette.json`, `mood/mood.md`.

### 3 · Imagem base (aula 009)
Para cada referência escolhida, o **bot da aula** (Claude CLI, `common/prompter.py`) escreve o
prompt olhando a referência e as imagens do mood: "o produto na exata mesma situação da
referência, com o mood"; "sessão nova sem viés" quando o prompt não entregou a ideia; troca de
rótulo pela sua marca (campo `brand`, `[extensão]`, 3 variações); upscale 2x importado e
conferido → `base/base_final.png` + `base/base.md` com a cadeia situação → rótulo → upscale.

### 4 · Storyboard (aula 010)
Instruções de edição uma por vez (presets literais da aula, "gerar 4 / gerar 1"), Draw to Edit
na UI, ideias importadas, 5 cenas em texto → `storyboard/scenes.json` + `storyboard.md`.

### 5 · Ângulos por cena (aula 011 + cena do produto, aula 013)
Por cena: base → "me traga outro ponto de vista…" → importar → escolher e ordenar → upscale;
aviso "acerte cores e luz antes do multishot" com a paleta → `shots/storyboard.json`.

### 6 · Animação (aula 012)
Por shot: prompt simples/elaborado/start-end, 2 takes, "like", nome `videos/cenaNN/shotMM_takeK.mp4`;
troca de modelo **sugerida** após 3 falhas; corte para preto como fallback → `animate/takes.json`.

### 7 · Trilha (aula 013)
Candidatas por upload/Downloads/histórico ou `sonilo_music` via CLI; escolha "sentindo" no player;
batidas e impactos detectados (numpy + ffmpeg) → `audio/music.*`, `audio/beats.json`, `license.txt`.

### 8 · Montagem no ritmo (aula 014)
Timeline dos takes escolhidos, cortes propostos nos impactos, velocidade com mistura de quadros,
pretos, offset da música, fade, SFX, último frame para transição colada → `edit/master.mp4`
(1920×1080/30 fps, H.264/AAC) — tudo por ffmpeg.

### 9 · Export e QA (aulas 007/014)
`16x9`, `9x16`, `1x1`, thumb e `qa_report.md` técnico (sem juízo estético). Reframe via CLI opcional.

### 10 · Publicar (aula 015)
Registro manual dos posts (rede, URL, feedback); portfólio pronto com **4 vídeos distintos**.

### 11 · Prospecção (aula 001)
Gate de 4 vídeos; leads; DM com o script literal (sem links, envio humano); teaser de 5–10 s com
música a partir de um take + trilha; follow-up para a call; `pitch.md` com a tabela de etapas.

## Estrutura

```
studio/
  app.py              núcleo da API (projetos, catálogo, estáticos) + montagem dos plugins
  steps.py            catálogo das 11 etapas (ordem, aula); `ready` vem dos plugins
  etapas/<id>/        plugin da etapa: META, router.py, view.html, view.js (descoberta automática)
  config.py           caminhos e layout        higgsfield.py  ponte com o CLI (subprocess --json)
  common/             ingest (imagem/vídeo/áudio), JobRegistry, ffmpeg, guide — API transversal das etapas
  <etapa>/service.py  serviço de cada etapa (refs, mood, base, storyboard, shots, animate, music, edit, export, publish, prospect)
  web/                shell da SPA: index.html, style.css, app.js + ui.js/ui.css (Studio.ui: componentes compartilhados)
tests/                pytest sem rede/navegador (serviços, API, ponte, plugins)
docs/                 contexto do projeto — ver CLAUDE.md (gitflow, dd, guidelines, adrs, domains, agents, plano)
projects/             dados dos projetos de vídeo (local, ignorado pelo git)
```

**Guia por etapa:** cada tela diz o que a aula manda fazer, o que falta e qual é a próxima ação —
calculado no backend lendo os artefatos do projeto (`studio/common/guide.py`, hook opcional
`studio/etapas/<id>/guide.py`). Rotas: `GET|PATCH /api/projects/{pid}` (campos `name, product,
vibe, aspect_ratio` `[extensão]`, `brand` `[extensão]`), `GET /api/projects/{pid}/guide` (as 11
etapas + progresso da campanha), `GET /api/projects/{pid}/guide/{etapa}` e
`GET /api/higgsfield/status?refresh=1` (cache de 60 s). Contrato para quem implementa etapa:
`docs/domains/studio/waves/wave-2-api-transversal.md`.

Variáveis: `STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`, `PORT`.

## Desenvolvimento

- Fluxo: `/dd` (Claude Code) como porta de entrada; SDD via Compozy (`.compozy/`).
- Gitflow: `docs/gitflow.md` — branch a partir de `develop`, PR para `develop`, trailer
  `Task-Id` (`OS-NNN` ou `ADH-OS-<data>-<seq>`), promoção `develop → main` por PR.
- CI: `.github/workflows/ci.yml` (ruff + pytest) e `task-id-check.yml`.
- Smoke visual fora do CI (ADR-008): `python scripts/smoke_ui.py http://127.0.0.1:8765 <pid> <pasta> [dark] [--timers]`
  — prints das 11 telas, erros de JS e prova de que nenhum timer sobrevive à troca de tela.
- Fidelidade ao curso: gates em `CLAUDE.md`. Melhorias fora do roteiro são sugeridas, não
  implementadas sem aprovação.

## O que fica fora do repositório

Vídeos, áudios, transcrições e o material bruto do curso (`*.mp4`, `*.srt`, `media/`,
`texts/`…) e a pasta `projects/` são locais — ver `.gitignore`.
