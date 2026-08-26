### FDD: prompter (o "bot" de prompts do curso, com Claude) — OS-012

Versão: 1.1 · Data: 2026-08-25 · Domínios: `mood` (consumidor inicial) + `common` (serviço transversal)

> **Correção de fidelidade (wave 2, OS-014).** O critério de aceite 4 desta versão dizia que todo
> prompt de mood devia sair "sem produto, sem pessoas, sem texto (aula 009)". A auditoria mostrou que
> a aula **não** diz isso: o mood board do instrutor tem o produto. O papel `ROLES["mood"]` perdeu
> "NO product, NO people, NO text, NO logos", `MOOD_GUARDS` ficou só com `("no people",)` e
> `enforce_mood_rules(result, no_people=True)` só acrescenta essa linha quando o usuário mantém o
> checkbox "sem pessoas" marcado. Ver `mood-guia-fidelidade-fdd.md` (OS-014).

### 1. Contexto e motivação técnica
Nas aulas 007, 009 e 012 o instrutor usa um GPT customizado ("Abrahub Creative Engine") para
transformar uma descrição, ou uma imagem anexada + instrução, em um prompt profissional em inglês
(câmera, lente, abertura, luz, estilo). Ele diz que "usar o ChatGPT normal também dá certo". O
Studio hoje substitui o bot por um template fixo que não olha imagem nenhuma — desvio de processo.
Esta feature repõe o bot com o **Claude CLI local** (assinatura do usuário, sem chave), com dois
modos, exatamente como o bot da aula 007 (guiado/simplificado) e da aula 009 (com imagem).

**Provides**: `studio/common/prompter.py` (`available`, `from_brief`, `from_images`, `fallback_template`);
`mood/vibe/` (imagens de vibe importadas) e `mood/prompts.json` (histórico de prompts gerados);
rotas `GET/POST /api/projects/{pid}/mood/vibe...` e `POST /api/projects/{pid}/mood/prompts/generate`.
**Consumes**: `project.json` (produto, vibe), `refs/candidates.json` (termos), imagens de `mood/vibe/`.
Etapas 3 (imagem base) e 6 (prompt de movimento) consumirão o mesmo serviço depois (fora deste FDD).

### 2. Objetivos técnicos
- Modo **brief** (sem imagem): produto, vibe, propósito, tom emocional, referência estética → prompt profissional.
- Modo **imagens + instrução**: 1–4 imagens de vibe + instrução livre do usuário → prompt fiel às imagens.
- Fallback determinístico (template atual) quando o CLI não existe ou falha; nunca bloquear a etapa.

### 3. Escopo e exclusões
Inclui: serviço, painel "Achar a vibe" na etapa 2 (importar imagens de vibe por upload/Downloads e
escolher até 4), seletor de modo, campos do brief, botão "Gerar prompt com Claude", histórico.
Exclui: geração de imagem (continua na UI/CLI da Higgsfield), uso em outras etapas, tradução.

### 4. Fluxos
Principal: usuário importa imagens de vibe → marca até 4 → escreve instrução ("bastante neon, neve,
sem pessoas") → Studio chama `claude -p` com as imagens (tool Read) e o papel do bot → recebe JSON
`{prompt, negative, camera, notes_pt}` → mostra no painel de prompt (editável) e grava em
`mood/prompts.json` → usuário copia e gera o grid de 4 na Higgsfield → importa → escolhe → mood.
Alternativo: sem imagem, o mesmo com o brief. Erro: CLI ausente → 409 com dica; timeout/JSON
inválido → 502 com o texto bruto; UI oferece o template como fallback.

### 5. Contratos públicos
- `GET /api/projects/{pid}/mood/vibe` → `{"available_claude": bool, "images": [candidatas de mood/vibe]}`
- `POST /api/projects/{pid}/mood/vibe/import/upload` (multipart `files`) → `{"added"}`
- `POST /api/projects/{pid}/mood/vibe/import/downloads` `{since_minutes}` → `{"added","scanned","folder"}`
- `POST /api/projects/{pid}/mood/prompts/generate` `{"mode": "brief"|"images"|"template", "instruction": str, "image_ids": [str], "purpose": str, "tone": str, "reference": str, "model": str}` → `{"prompt","negative","camera","notes_pt","source","mode","ui_hint","aspect_ratio","images":[ids]}`; 422 se `images` sem ids; 409 se Claude indisponível nos modos que exigem; 502 se a chamada falhar.
- `GET /api/projects/{pid}/mood/prompts/history` → lista dos gerados (mais recente primeiro).

### 6. Erros e fallback
`prompter.available()` falso → 409 (a UI desabilita os modos com Claude e mantém o template);
`subprocess.TimeoutExpired` (180 s) → 502; resposta sem bloco JSON → 502 com `raw`.

### 7. Observabilidade
`mood/prompts.json` guarda modo, instrução, ids das imagens, duração da chamada e o prompt.

### 8. Dependências
`claude` no PATH (`~/.local/bin/claude`); permissão `--allowedTools Read` só para os arquivos das imagens.

### 9. Critérios de aceite
1. Com CLI fakeado, `from_images` monta o comando com `-p`, `--allowedTools Read`, caminhos das imagens e devolve o JSON parseado.
2. `from_brief` sem CLI cai no template e marca `source: "template"`.
3. `POST /mood/prompts/generate` modo `images` sem ids → 422; com CLI ausente → 409.
4. ~~Prompt gerado (qualquer modo) obedece à aula 009: sem produto, sem pessoas, sem texto.~~
   **Substituído em 1.1 (OS-014):** o prompt de mood **não** recebe negativo nenhum por conta própria;
   com `no_people` marcado (padrão da tela, sugestão da aula), o serviço garante "No people." e nada mais.
5. Imagens de vibe importadas aparecem em `mood/vibe/` e são selecionáveis (≤ 4).
6. Histórico persiste e é listado.

### 10. Riscos
Custo/latência do CLI (~10–20 s por chamada): botão com estado "gerando…". Claude sem sessão: 409 com dica `claude login`.

### 11. Build order
`studio/common/prompter.py` → `studio/mood/service.py` (vibe + generate_prompt + histórico) →
`studio/etapas/mood/router.py` → `view.html`/`view.js` → `tests/test_prompter.py`, `tests/test_mood_service.py`, `tests/test_api.py`.
