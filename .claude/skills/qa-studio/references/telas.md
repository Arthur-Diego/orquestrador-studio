# Catálogo de telas e comandos (qa-studio)

Fonte de verdade em runtime: `GET /api/steps` (`status: ready | soon`) — só telas `ready` entram na
rodada; `soon` fica BLOQUEADO no relatório. Este catálogo é a **lista de comandos** que cada tela
precisa ter coberta em `scripts/qa/cenarios/<tela>.py`; comando sem caso é lacuna a fechar no
Passo 3 (codificar o caso antes de executar). Ids aceitos na invocação: `refs mood base storyboard
animate music edit export publish prospect` (ou 1..10), `overview shell moodboards creditos`.

Não exercitar em modo offline: `POST /api/pinterest/login` e `#btnLogin` (abrem Chromium real),
`POST /api/moodboards/{mbid}/open-folder` e `#btnMbOpenFolder` (abrem o explorer do SO), gerações
`--real`. Em offline, gerar/custo/histórico batem nos fakes (`scripts/qa/fakes/`).

## Shell (todas as telas) — `studio/web/index.html`, `app.js`, `ui.js`  → `cenarios/shell.py`

Sidebar `#projSel` (troca de campanha), `#btnNewProj` → wizard (`#cfName` obrigatório, `#cfProduct`,
`#cfVibe`, radio `aspect` 16:9/9:16/1:1, Cancelar/Criar), `#btnOverview`, `#btnMoodboards`,
`#btnCreditos`, `#railPipe`/`#railCount`, `#steps li.ready` (click + Enter/Espaço), `#hfChipSide`,
`#btnTheme` (auto→light→dark, `localStorage["studio.theme"]`). Topbar `#tbName`, `#tbMeta`,
`#btnCredits`, `#tbPipe`/`#tbCount`, `#btnEditCamp` → modal editar, `#btnContinue` → `guide.current`.
Injetados em cada etapa: `#guide`, botão `.shell-reset` "Resetar etapa [extensão]" → modal listando a
cascata → `POST /steps/{step}/reset`. Overview: `#btnResetCamp` → `POST /reset`. `#toast`.
Rotas: pid inexistente → 1ª campanha; view inexistente → overview; `#/moodboards`, `#/creditos`.

## Overview — `renderOverview()` → `cenarios/overview.py`

Cards por etapa (`.ovgrid`, `[data-go]` Abrir/Rever/Continuar aqui), chips de resumo `.ov-summary`,
texto "Você está na etapa N", campanha vazia. Inconsistência conhecida: eyebrow "Etapas 1 a 11".

## 1 · refs — `studio/etapas/refs/` + `studio/refs/service.py` → `cenarios/refs.py`

`#brand` + `#btnSaveBrand` (`PUT /refs/validated-brand`), `#terms`, `#maxPer` (5–100), `#headed`,
`#btnSuggest` (`GET /api/suggest-terms`), `#btnSearch` (`POST /refs/search` → job; offline: erro
amigável, UI não trava), upload `#refsUpload`/`#btnBring` (`POST /refs/import/upload` →
`refs/candidates/`), grid multi-seleção + `#btnSave` (`POST /refs/select` → `refs/brainstorming/`),
"limpar filtros". Disco: `refs/candidates/`, `refs/brainstorming/`, `refs/validated_brand.json`.

## 2 · mood — `studio/etapas/mood/` + `studio/mood/service.py` → `cenarios/mood.py`

ADR-014: a etapa escolhe e aplica um board da biblioteca. `#panelPick` (boards de `GET /api/moodboards`),
`#btnApplyBoard` (`POST /mood/pull/{mbid}` → `mood/`), `#panelCurrent` (`GET /mood`), `#btnSwap`,
`#btnManageBoards` → `#/moodboards`, "Ir para a biblioteca". Estado vazio (biblioteca sem board com
seleção). Disco: `mood/mood.md`, `mood/palette.json`, `mood/selected/`.

## 3 · base — `studio/etapas/base/` + `studio/base/service.py` → `cenarios/base.py`

P01: fontes (`GET /base/mood-sources`), `#promptInstruction`, `#btnPrompt` / `#btnPromptNoBias`
(`POST /base/prompts/generate` → claude fake, modal de progresso), "Copiar", histórico
(`GET /base/prompts/history`), `#btnBasePanel01Cli` (custo → `POST /base/cost` → gerar). P02
`[extensão]`: `#brandName`, `#brandDesc`, `#btnBrand` (`POST /base/brand` → `base/brand.json`). P03:
candidatas (`GET /base/candidates`), `#baseUpload`, `#btnBaseDownloads` (`STUDIO_DOWNLOADS`),
`#btnBaseHistory` (fake: 3 imagens), `#btnBaseSelect` (`POST /base/select` → `base/base_final.png`),
`#btnBaseCli` (custo → `POST /base/generate` → job → candidata nova).

## 4 · storyboard — `studio/etapas/storyboard/` + `studio/storyboard/service.py` → `cenarios/storyboard.py`

P01 ideias: `#sbCounts` → modal importar (upload / Downloads / histórico), `#sbKind`, `#sbPreset`,
`#sbText`, `#sbGen4`/`#sbGen1` (custo → `POST /storyboard/generate` → job), `#sbCopy`, seleção
(`POST /storyboard/candidates/select` → `storyboard/ideas/`). P02 cenas: `#sbAdd`, `#sbReorder`
(modal ↑↓), `#sbRender` (`POST /storyboard/render` → `storyboard/storyboard.md`), `#sbSave`
(`PUT /storyboard/scenes` → `scenes.json`); por cena: "Gerar prompt de vídeo" (`POST /storyboard/
video-prompt`), modal "Gerar animação" (modelo/duração/start-end → `POST /storyboard/video/generate`
→ job → MP4), lightbox. P03/P04 ângulos (`/storyboard/angles/scenes/{scene}/…`): `#scenePanel`,
`#shotsCounts` importar, `#shotsUpscaled`, `#btnShotsSave`, `#promptKind/#promptSubject/#promptScale/
#promptAngle` + `#btnPrompts`, "base ▾" / "Usar como base da cena" / "Imagem base da campanha" /
"Imagem da cena", "remover", upscale. Produto: `/storyboard/angles/product/…` (ref, candidatas,
select, upscale). Disco: `storyboard/scenes.json`, `storyboard.md`, `storyboard/cena01/`, `product/`.

## 5 · animate — `studio/etapas/animate/` + `studio/animate/service.py` → `cenarios/animate.py`

`#anReload` (`GET /animate/shots`), por shot: "Sugerir prompt" (`GET /animate/prompt`), takes
(`POST …/takes`), like (`POST …/takes/{take}/like`), modal gerar (custo `POST /animate/cost` →
`POST /animate/generate` 202 → `GET /animate/job`; modelos `kling2_6`, `seedance_2_0`), P02 `#anDrop`/
`#anUpload` (mp4), `#anBtnDownloads`, `#anBtnHistory`. Disco: `animate/takes.json`, `videos/<cena>/`.

## 6 · music — `studio/etapas/music/` + `studio/music/service.py` → `cenarios/music.py`

`#btnMusStory` (`POST /music/story/render` 202 → ffmpeg → `audio/rough_sequence.mp4`, progress),
radio `musClosed` + `#btnMusStoryCheck` (`POST /music/story/check`), `#musCounts`/`#musUpload`
(`POST /music/import/upload`), player por candidata, "Escolher" (`POST /music/select` →
`audio/music.mp3` + `license.txt`), batidas (`POST /music/beats` → `audio/beats.json`), geração
`sonilo_music` (custo → `POST /music/generate` 202 → job).

## 7 · edit — `studio/etapas/edit/` + `studio/edit/*.py` → `cenarios/edit.py`

Barra: `#edBack`, `#edUndo`/`#edRedo` (Ctrl+Z / Ctrl+Shift+Z), `#edSave`/`#edSaveBtn`, `#edAuto`,
`#edAspect`/`#edRes`/`#edFps`, `#edGuide` (modal aula 014), `#edFull`, `#edExport` (modal master |
rough → `POST /edit/render` → `GET /edit/render/job` → `edit/master.mp4` / `rough_cut.mp4`). Rail
`#edRail`: Mídia (`#mUpload` → `POST /edit/media/upload`, `#mReset` "montar a partir dos takes com
like" → `POST /edit/timeline/reset`), Texto, Legendas (`#capGen`, add/delete), Áudio/SFX (`#sfxUp` →
`POST /edit/sfx/upload`), Transições, Efeitos, Filtros, Elementos, Ajustes, Biblioteca. Player
`#pcStart #pcPrev #pcPlay #pcNext #pcEnd #pcLoop #pcMute #pcFs` (Space, ←/→). Props `#edProps`:
transform, vídeo (in/out/zoom), áudio, velocidade `[data-sp]`, cor + `#cReset`, texto `#txSh/#txUp`,
música `#mMute`, projeto `#pFade/#pLoud`. Timeline: `#tSplit` (Ctrl+B), `#tDup` (Ctrl+D), `#tDel`
(Delete), `#tRipple`, drag/resize. Persistência `PUT /edit/timeline` → `edit/timeline.json`;
`POST /edit/propose-cuts`, `POST /edit/last-frame`.

## 8 · export — `studio/etapas/export/` + `studio/export/service.py` → `cenarios/export.py`

Formatos (`GET /export/list`, `/export/status`), "Renderizar" (`POST /export/render` → job →
`export/9x16.mp4` …), "Ver arquivo", `#btnRenderAll`, preview/thumb (`POST /export/preview`,
`/export/thumb`), `#btnQa` (`POST /export/qa` → `export/qa_report.md`), reframe via CLI
(`POST /export/reframe/cost` → `/export/reframe`). Estado sem `edit/master.mp4` → 404 amigável.

## 9 · publish — `studio/etapas/publish/` + `studio/publish/service.py` → `cenarios/publish.py`

`#pubVideo` (`GET /publish/exports`), `#pubNetwork` (datalist), `#pubDate`, `#pubUrl`, `#pubNote`,
`#btnPubAdd` (`POST /publish/log` 201; validação), lista (`GET /publish/log`), feedback
(`POST …/feedback`), "Remover" (`DELETE …/{post_id}`), comunidade `[data-com]` (`POST /publish/
community`), portfólio (`GET /publish/portfolio`, `GET /api/portfolio` global). Disco: `publish/log.json`,
`community.json`, `portfolio.md`.

## 10 · prospect — `studio/etapas/prospect/` + `studio/prospect/service.py` → `cenarios/prospect.py`

`#gatePanel` (`GET /prospect/gate` — 4 vídeos publicados; comparar cheio × vazio), `#btnNewLead` +
`#lfBusiness #lfHandle #lfPostRef #lfWhy #lfSegment #lfRole` + "Cadastrar lead" (`POST /prospect/
leads`; validação), por lead: "Gerar DM" (`GET …/dm`), "Copiar DM", "Marquei como enviada"
(`POST …/sent`), "Marcar respondeu" (`POST …/replied`), teaser (`POST …/teaser` → job → `prospect/
teasers/`), "Copiar follow-up" (`GET …/followup`), "Registrar call" (`POST …/call`), "Remover"
(`DELETE`), pitch `#btnPitchCopy`, `#btnPitchSave` (`POST /prospect/pitch` → `prospect/pitch.json`).

## G1/G2 · moodboards — `studio/web/moodboards.js` + `studio/moodboards/` → `cenarios/moodboards.py`

Lista `#/moodboards`: grid (`GET /api/moodboards`), `#btnNewBoard`/`#btnNewBoard2` → modal (`#mbName`
obrigatório, `#mbNote`; duplicado → 409). Editor `#/moodboards/<mbid>`: `#mbBack`, `#btnMbRename`
(`PATCH`), `#btnMbDelete` (modal → `DELETE`), P01 `#mbDrop`/`#mbUpload`, `#btnMbDownloads`,
`#btnMbHistory`; P02 `#mbCounts`, seleção + `#btnMbSave` (`POST …/select` → `images/`), paleta
`#mbPalette`, "usar no board", "▨ ângulos" (multishot: `POST …/multishot/cost` → `/generate` → job),
remover candidata (`DELETE …/candidates/{cid}`); P03 `#mbMode` (template/brief/images),
`#mbInstruction`, `#mbNoPeople`, `#btnMbGenPrompt` (`POST …/prompt/generate`). Não clicar
`#btnMbOpenFolder`.

## G3 · creditos — `studio/web/creditos.js` + `studio/creditos/` → `cenarios/creditos.py`

Saldo + `#crRefresh` (`GET /api/creditos/balance`), tabela admin de modelos default por ação com
escopo Global / Esta campanha (`[data-scope]`; `PUT /api/creditos/config` → `STUDIO_STATE/config.json`;
`PUT /api/projects/{pid}/creditos/config`; `.cr-clear` → `DELETE …/config/{action}`), tabela de custo
(`GET /api/creditos/cost`, `/models`), histórico (`GET /api/creditos/history`; gasto via
`POST /api/creditos/spend` ou geração fake), `GET /api/projects/{pid}/creditos`.
