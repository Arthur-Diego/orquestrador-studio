# Orquestrador Studio

Ferramenta local para executar, **etapa por etapa e sem desviar do roteiro**, o método de
produção de vídeo com IA do curso *"O Orquestrador — Iniciante"* (ABRAhub): referências →
mood board → imagem base → storyboard → ângulos → animação → trilha → montagem → export →
publicação → prospecção. Backend FastAPI + frontend estático; sem build, sem banco.

**Estado (2026-08-25):** etapas **1 — Referências** e **2 — Mood board** implementadas. As
demais aparecem no menu como "em breve". Plano completo em `docs/plano/`.

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
Crie um projeto (nome, produto, vibe). "Sugerir termos" → "Buscar e baixar": o scraper
Playwright percorre o Pinterest em ritmo humano com a sua sessão (login opcional; perfil em
`~/.orquestrador-studio/pinterest-profile`), baixa as imagens em maior resolução para
`projects/<id>/refs/candidates/` e você marca as que gosta. "Salvar seleção" copia para
`refs/brainstorming/` e registra origem em `refs/README.md`.
Aviso: automatizar o Pinterest contraria os termos dele — use uma conta secundária. As
imagens são só referência de mood; nunca entram no vídeo final.

### 2 · Mood board (aula 009)
**Uma vibe só.** O Studio gera **um prompt de vibe** (ambiente, luz, cor — sem produto, sem
pessoas) a partir das referências escolhidas; você gera um grid de 4 na interface da
Higgsfield (onde o ilimitado do plano vale) ou via CLI (gasta créditos); "Nova variação"
troca só a estilização, como ajustar o *Stylization* e regerar. Importe por arrastar,
pela pasta **Downloads do Windows** ou pelo **histórico do CLI**; escolha até 8 imagens no
mesmo mood → `mood/selected/`, `mood/palette.json`, `mood/mood.md`.

## Estrutura

```
studio/
  app.py              API + estáticos          steps.py   catálogo das 11 etapas (aula, status)
  config.py           caminhos e layout        higgsfield.py  ponte com o CLI (subprocess --json)
  refs/pinterest.py   scraper Playwright       refs/service.py  projetos, jobs, seleção
  mood/service.py     prompt de vibe, import, seleção, paleta
  web/                index.html, style.css, app.js
tests/                pytest sem rede/navegador (serviços, API, ponte)
docs/                 contexto do projeto — ver CLAUDE.md (gitflow, dd, guidelines, adrs, domains, agents, plano)
projects/             dados dos projetos de vídeo (local, ignorado pelo git)
```

Variáveis: `STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`, `PORT`.

## Desenvolvimento

- Fluxo: `/dd` (Claude Code) como porta de entrada; SDD via Compozy (`.compozy/`).
- Gitflow: `docs/gitflow.md` — branch a partir de `develop`, PR para `develop`, trailer
  `Task-Id` (`OS-NNN` ou `ADH-OS-<data>-<seq>`), promoção `develop → main` por PR.
- CI: `.github/workflows/ci.yml` (ruff + pytest) e `task-id-check.yml`.
- Fidelidade ao curso: gates em `CLAUDE.md`. Melhorias fora do roteiro são sugeridas, não
  implementadas sem aprovação.

## O que fica fora do repositório

Vídeos, áudios, transcrições e o material bruto do curso (`*.mp4`, `*.srt`, `media/`,
`texts/`…) e a pasta `projects/` são locais — ver `.gitignore`.
