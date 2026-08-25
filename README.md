# Orquestrador Studio

Ferramenta local para executar, etapa por etapa, o método de produção de vídeo com IA do curso
"O Orquestrador — Iniciante" (ABRAhub). Backend FastAPI + frontend estático; sem build.

**Estado:** apenas a **Etapa 1 — Referências** (aula 009) está implementada. As demais aparecem
no menu como "em breve".

## Rodar

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
# Chromium do Playwright: se não houver em ~/.cache/ms-playwright → playwright install chromium
./run.sh            # http://127.0.0.1:8765
```

## Etapa 1 — Referências (Pinterest)

1. Crie um projeto (nome, produto, vibe). Isso cria `projects/<ano-mes-slug>/` com a árvore
   `refs/candidates`, `refs/brainstorming`, `mood`, `images`, `videos`, … (organização da aula 009/011).
2. "Fazer login no Pinterest" abre um Chromium com janela (WSLg); logue uma vez — a sessão fica em
   `~/.orquestrador-studio/pinterest-profile`. Use de preferência uma conta secundária.
3. Informe termos (ou "Sugerir termos") e clique "Buscar e baixar". O scraper rola a busca em ritmo
   humano, baixa as imagens em maior resolução para `refs/candidates/` e gera miniaturas.
4. Marque as que você gosta e "Salvar seleção": copiam-se para `refs/brainstorming/` e
   `refs/README.md` registra termo e origem de cada uma.

Funciona sem login (testado: 20 imagens em 2 buscas), mas sem sessão o Pinterest serve "gated pins"
e o link da página do pin (`pin_url`) fica vazio — só a URL da imagem é registrada. Logado, o card
traz `/pin/<id>` e ele entra no README.

Aviso: automatizar o Pinterest contraria os termos de uso dele; o risco é da conta usada.
As imagens servem só como referência de mood — nunca entram no vídeo final.

## Etapa 2 — Mood board ("modo UI")

Objetivo: usar o **ilimitado da UI da Higgsfield** (que não vale no CLI) sem automatizar a interface.

1. **Prompts**: 6 prompts de mood (ambiente, produto, escala, textura, luz, contraponto) gerados a partir do
   produto/vibe do projeto e das referências escolhidas na etapa 1. Botões "Copiar"/"Copiar todos".
2. Você gera na UI (Nano Banana Pro 2K, 16:9) e o Studio **importa** por um destes caminhos:
   - arrastar/enviar arquivos;
   - **pasta Downloads do Windows** (detectada em `/mnt/c/Users/<você>/Downloads`; override `STUDIO_DOWNLOADS`),
     só imagens dos últimos N minutos;
   - **histórico do CLI** (`higgsfield generate list --image --json`) — exige `higgsfield auth login`
     (e `hf workspace set`); parser defensivo, ainda não validado com uma conta logada.
   - Alternativa paga: "Gerar via CLI" (`higgsfield generate create nano_banana_2|gpt_image_2`), com as
     referências da etapa 1 como `--image-references`.
3. Escolha as imagens → "Salvar mood": `mood/selected/`, `mood/palette.json` (6 cores dominantes) e `mood/mood.md`.

O CLI (`@higgsfield/cli` 1.1.23) está instalado globalmente via npm; `studio/higgsfield.py` é a ponte
(sempre via subprocess + `--json`, nunca chamando a API direto — regra da doc oficial).

## Estrutura

```
studio/
  app.py            API + arquivos estáticos
  config.py         caminhos (STUDIO_PROJECTS, STUDIO_STATE)
  steps.py          etapas do curso (menu)
  refs/pinterest.py scraper Playwright
  refs/service.py   projetos, jobs, seleção
  web/              index.html, style.css, app.js
projects/           dados dos projetos (gitignore)
```
