# Auditoria de fidelidade — Etapas 1, 2 e 3 (aula 009 + regras gerais 005–008)

Wave 2 · 2026-08-25 · auditor read-only (subagente)

**Escopo lido (integral):** `texts/001, 003–009` (resumos de página, ~5 KB cada, cortados em ~5,6 KB pelo harvester) **e** as transcrições Whisper completas em `media/00X--….txt` (a aula 009 tem 24 KB; é dela que saem as frases literais abaixo). Planos: `docs/plano/plano-automacao-videos.md`, `docs/plano/plano-higgsfield.md`. Código na branch `develop` de `/home/arthu/code/senhortecnologia/orquestrador-studio`. Nada foi editado.

**Nota sobre as fontes:** os arquivos em `texts/` são a descrição da página da aula (resumo editorial da ABRAhub), não a fala do instrutor. As citações "literais" deste relatório vêm de `media/*.txt`. Onde o resumo de página e a transcrição divergem, prevalece a transcrição.

---

## 0. Resumo executivo

| Etapa | Fidelidade geral | Achado mais grave |
|---|---|---|
| 1 Referências | **Boa.** Reproduz "Pinterest → salvar o que gosta → brainstorming" | Sugestão de termos busca por *produto*, a aula busca por **marca validada** ("Red Bull"); campo "por quê" do README nunca é preenchido pela tela |
| 2 Mood board | **Média.** Estrutura certa (1 vibe, grid de 4, teto 8), bot reproduzido | Regra codificada **"NO product"** contradiz a aula (as imagens de mood do instrutor **têm a lata**); a tela atribui essa regra à "aula 009". CLI usa `refs/brainstorming` como referência de imagem em vez da imagem de vibe |
| 3 Imagem base | **Média-baixa.** Cadeia situação→rótulo→upscale e `base_final.png` corretos | A aula gera o prompt de situação **com o bot olhando a referência**; o Studio entrega um **template fixo** e não chama `prompter` (ROLES["base"] existe e não é usado). `prompt_no_bias` é instrução para o GPT, mas a tela manda "colar na Higgsfield" |
| Regras gerais 005–008 | **Boa** no essencial (processo > plataforma; prompt em inglês; custo antes de gerar) | Formato (16:9) fixo e `vibe` pedido na criação do projeto invertem a ordem da aula; `PROJECT_LAYOUT` não "espelha" a aula como o comentário afirma |

---

## Etapa 1 — Referências (`refs`)

### 1.1 O que a aula ensina (009, transcrição)

1. **Objetivo declarado:** destravar ideias sem "tirar coelho da cartola": *"o que eu vou te ensinar aqui também é um processo pra que você tenha ideias […] pra que você possa se inspirar no trabalho de outras pessoas."*
2. **Duas fontes:** Pinterest (principal, "algo real") e a aba **Explore do Midjourney** (*"que também é muito boa"*, busca "Ads", "Soda Ads").
3. **Busca por marca validada, não por categoria:** *"vamos colocar uma marca conhecida de alguma coisa que já tá validada. […] Red Bull […] eles já têm anúncios já validados."* Depois refina por situação: *"Red Bull Snow"*, *"Red Bull Snow Ads"*.
4. **Criar a pasta do projeto antes de salvar:** *"Pra todo projeto que você for criar, crie uma pasta […] campanha de energético. […] Imagens. […] vídeos. […] dentro de imagens, eu vou colocar brainstorming."*
5. **O que vai para brainstorming:** *"imagens que não necessariamente vão fazer parte da minha campanha, mas elas estarão aqui pra que eu possa acessá-las"*; *"vou salvando em brainstorming as imagens que eu gosto […] que a gente talvez possa usar de mood."*
6. **Critério de escolha = gosto + fugir do clichê:** *"muito padrãozinho, mostrando a lata, com fundo preto. Eu quero fugir disso."*; *"Você não precisa ter ideia nenhuma ainda. Só vai salvando o que você gosta."*
7. **Rolar o "buraco de minhoca":** *"o Pinterest é bom que ele vai me dando referências de coisas parecidas […] A gente vai entrando num buraco de minhoca."*
8. **Revisar e apagar:** *"Agora que eu já vi as de gelo, eu nem gosto muito mais dessa. Então, eu vou deletar essa."* (ele apaga 2 das ~8 salvas).
9. **Quantidade:** sem número; ele para em ~6 imagens (*"Acho que eu já tenho imagens suficientes"*).
10. **Saída:** pasta `imagens/brainstorming/` com as referências mantidas. Nada é feito com elas ainda (*"por enquanto, a gente não vai fazer nada com essas imagens"*).
11. **Regra de qualidade repetida:** referências soltas não fecham uma campanha — *"a gente não pode utilizar essas referências tão isoladas. Então, nós precisamos de um mood"* (ponte para a etapa 2).

### 1.2 O que a implementação faz

- `POST /api/projects` cria `projects/<YYYY-MM-slug>/` com `PROJECT_LAYOUT` (`config.py:15-20`) e `project.json {name, product, vibe}`.
- `GET /api/suggest-terms?product&vibe` → `service.suggest_terms` (`refs/service.py:59-67`): 5–8 termos derivados do **produto** ("`{p} ad campaign`", "`giant {p} advertising`"…).
- `POST …/refs/search` → thread com `pinterest.search` (Playwright, perfil persistente, ritmo humano, teto por termo, dedupe SHA-1, thumbs) → `refs/candidates/*.jpg` + `candidates.json`.
- Galeria: clique marca/desmarca; `POST …/refs/select {ids, notes}` copia para `refs/brainstorming/<id>.jpg`, apaga desmarcadas, escreve `refs/README.md` (`service.py:128-148`). A tela envia **só `ids`** (`view.js:72`), `notes` fica sempre vazio.
- HLD `docs/domains/refs/hld.md` descreve exatamente isso; ADR-005 registra o risco de ToS do Pinterest.

### 1.3 Divergências

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção |
|---|---|---|---|---|---|
| R1 | desvio de processo (leve) | *"vamos colocar uma marca conhecida […] que já tá validada. Red Bull"*; refinos "Red Bull Snow", "Red Bull Snow Ads" | `refs/service.py:59-67` gera termos só a partir de `product`/`vibe`; nem `project.json` nem a tela têm "marca de referência" | média | Adicionar campo opcional "marca(s) validada(s) para se inspirar" ao sugerir termos: `{brand} ads`, `{brand} {vibe}`, `{brand} {vibe} ads`; manter os termos por produto como complemento |
| R2 | falta | *"ou você pode usar a aba Explore do próprio Midjourney […] Ads"* | Nenhuma menção na tela da etapa 1 (`view.html`); só a etapa 2 fala em Explore | baixa | No painel-guia da etapa 1, listar Explore/MJ como fonte manual (upload das imagens salvas); opcional: botão "Adicionar por upload" em `refs/candidates` |
| R3 | texto da tela enganoso | *"imagens que não necessariamente vão fazer parte da minha campanha"* | `view.html:4` "nada entra no vídeo final"; `service.py:136` README "Nunca entram no vídeo final (aula 009)" | baixa | A regra "nunca no output" é do plano (direitos), não da aula. Reescrever: "servem de inspiração e de referência para os prompts; por direitos autorais, não entram no vídeo (regra do Studio)" |
| R4 | extensão não marcada | — (a aula não escreve "por quê") | `service.py:135,142-143` README com "por quê"; `SelectReq.notes` (`router.py:18-20`) | baixa | Ou expor o campo na galeria (input curto por card) e marcar `[extensão]`, ou remover `notes`/"por quê" do README |
| R5 | desvio de processo (ordem) | *"Você não precisa ter ideia nenhuma ainda"*; o mood é **encontrado** na etapa 2 | `index.html:23` pede `vibe` ao criar o projeto; `suggest_terms` usa `vibe` | baixa-média | Tornar `vibe` claramente opcional/"preencha depois", ou movê-lo para ser gravado pela etapa 2 (`mood.select(note)` já tem "vibe em palavras") |
| R6 | ok | *"vou salvando […] o que eu gosto"*; apaga depois | seleção/desseleção reflete em `brainstorming/` (`service.py:137-145`) | — | — |
| R7 | ok | pasta `imagens/brainstorming` | `refs/brainstorming` (troca de nome de pasta = ferramenta, não processo) | — | ver §5 sobre `PROJECT_LAYOUT` |
| R8 | ok (ferramenta) | Pinterest na UI logada | Playwright com sessão do usuário, ADR-005 | — | Manter aviso de ToS (já existe em `view.html:31`) |

### 1.4 Texto sugerido para o painel-guia

**O que fazer nesta etapa**
Comece sem ideia nenhuma. Pesquise no Pinterest uma marca já validada do seu segmento (ex.: "Red Bull", depois "Red Bull snow ads") e role o "buraco de minhoca" que o Pinterest abre. Marque só o que você gosta e o que foge do clichê — nada de "lata com fundo preto". Se quiser, traga também imagens salvas do Explore do Midjourney. Ao salvar, as escolhidas vão para `refs/brainstorming/`; depois de ver tudo, volte e desmarque o que já não te agrada.

**Checklist de qualidade da aula**
- Busquei por uma marca validada, não só pela categoria do produto
- Salvei o que **gosto**, sem me prender ao produto ("não tem nada a ver com Red Bull, mas gostei do conceito")
- Fugi do padrão que "todo mundo já viu"
- Revisei e apaguei o que deixou de me agradar
- Ainda não tentei decidir a campanha — isso vem depois do mood

**Entradas necessárias:** projeto criado (nome + produto); sessão do Pinterest (opcional, melhora os resultados).
**Saída esperada:** `refs/brainstorming/*.jpg` (as referências mantidas) + `refs/candidates/candidates.json` com `selected=true`.

### 1.5 Validações automáticas possíveis

| Regra | Objetivo | Fonte |
|---|---|---|
| `candidates.json` tem ≥ 1 item `selected` com arquivo em `refs/brainstorming/` | bloquear a etapa 3 (já feito em `base/service.py:158-160`) | aula: sem refs não há "situação" |
| ≥ 3 referências escolhidas (aviso, não bloqueio) | a aula mantém ~6 | [inferência do exemplo] |
| Cada `selected` tem cópia em `brainstorming/` e vice-versa (invariante do HLD) | consistência | HLD refs |
| Termos de busca com ≥ 1 termo contendo nome de marca (aviso) | "marca validada" | aula 009 |
| Nenhum `selected` com `alt` contendo "save pin/pinterest" (lixo do DOM) | qualidade | — |

---

## Etapa 2 — Mood board (`mood`)

### 2.1 O que a aula ensina (009, transcrição)

1. **Por que:** *"pra que a sua campanha fique consistente […] a gente não pode utilizar essas referências tão isoladas. Então, nós precisamos de um mood, uma vibe."*
2. **Onde achar a vibe:** Explore do Midjourney, *"porque a gente tem prompt aqui pra utilizar. […] copiar o prompt dessa pessoa e criar ali pra mim."* Busca em inglês (*"Drink Ice"*, *"Snow Commercial"*, *"Snow, neon, commercial"*).
3. **Critério: sentimento, não assunto:** *"o que a gente vai encontrar aqui agora não precisa ter a ver com […] esse tipo de campanha. A gente só precisa gostar do mood, da estética, do sentimento que a imagem passa."* Evita imagem *"focada demais no rosto"* porque *"a gente tá trabalhando com um produto"*.
4. **Decisão:** *"Esse aqui vai ser o mood da nossa campanha. […] Tem neve e tem neon, que traz essa sensação de energia."*
5. **Primeira geração:** *"copiar esse prompt e pedir pra criar um quadro com quatro imagens diferentes."* Se parecidas demais → *"modificar a estética […] Stylization […] um pouco mais forte."*
6. **Se não pegou a vibe → bot com imagem:** *"vou voltar na imagem que eu gostei. Vou pegar ela de referência […] no meu bot […] Simplificado."* Anexa **duas** imagens (*"Essa é o mood e essa aqui é a imagem que eu gostei"*) e escreve: *"Quero uma imagem para uma campanha de energético que tenha o mood parecido com o da primeira imagem fornecida. Bastante neon, neve e basicamente a mesma estética aplicada nessa imagem. Porém, eu não tenho nenhum interesse em pessoas. É um comercial de energético."* Sem bot: *"Usa só o ChatGPT normal […] também vai dar certo."*
7. **Resultado do mood contém o produto:** *"ele já me deu inclusive o Red Bull […] é exatamente isso que eu quero. Essa é a vibe. Então eu já tenho o meu mood."* E depois: *"Gostei muito da noite, a lata aqui."*
8. **Segunda rodada com referência de estilo:** pega a melhor do grid → *"o que eu quero é referência de estilo"* (não Image Prompt, não Omni) → *"mesmo prompt"* → 4 imagens → *"todas mais ou menos no mesmo mood. Vou pegar todas elas e vou salvar elas na minha pasta [de mood]."*
9. **Pasta:** *"Aqui na minha pasta de brainstorming, eu vou criar aqui o meu mood board"* → *"download dessas imagens para a minha pasta de mood"*.
10. **Mood board como filtro:** cria Moodboard no MJ (*"Campanha, energético, neve"*), upload de todas; *"tudo que eu for criar aqui, ele vai se inspirar nessa vibe"*. Demonstra com/sem mood board: sem → *"muito estranha"*; com → *"bem mais próximo"*.
11. **Alternativa sem Midjourney (ferramenta):** Higgsfield Soul *Color Transfer* ou Nano Banana Pro com imagem de referência: *"Quero que utilize a imagem fornecida como referência de mood. Mas cria uma imagem totalmente diferente."* → *"pegou mais ou menos a paleta de cores […] é contornável."*
12. **Realismo via mood board de filme:** *"pegar o mesmo prompt e utilizar um mood board de algum filme"* → homem "muito mais realista". Pack de mood boards no nível 2.

### 2.2 O que a implementação faz

- Painel 1 "Achar a vibe": upload/Downloads para `mood/vibe/candidates/`, escolher até 4 (`service.py:79`, `view.js:102`).
- Painel 2 "Prompt de vibe (o bot)": `POST …/mood/prompts/generate` com `mode ∈ {images, brief, template}` → `common/prompter.py` (`claude -p`, com `--allowedTools Read` para imagens) → JSON `{prompt, negative, camera, notes_pt}`; **sempre** passa por `enforce_mood_rules` (`service.py:140`, `prompter.py:152-161`) que injeta "No product. No people. No text." se faltarem. Template fixo em `suggest_prompts` (`service.py:51-75`) com 4 variações de estilização (`_STYLE_VARIANTS`) e frase "Inspired by real campaign references: {termos e alts do Pinterest}".
- Botão "Gerar imagens via CLI": `POST …/mood/generate` usa `refs/brainstorming/*.jpg[:6]` como `image_references` (`router.py:147`, `service.py:187-189`), custo antes (`/mood/cost`) e `confirm()`.
- Painel 3: importar grid (upload / Downloads / `generate list --image`).
- Painel 4: `select` ≤ 8 (`service.py:233-235`) → `mood/selected/`, `palette.json` (6 cores por quantização), `mood.md` com `note`.
- Docs: `hld.md:10-14` e `prompter-fdd.md:58` fixam "sem produto, sem pessoas, sem texto" como regra da aula; CLAUDE.md cita a correção "1 prompt de vibe × grid de 4".

### 2.3 Divergências

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção |
|---|---|---|---|---|---|
| M1 | **desvio de processo + texto enganoso** | O mood **tem o produto**: *"ele já me deu inclusive o Red Bull […] Essa é a vibe"*; *"Gostei muito da noite, a lata aqui"*. A aula só diz *"não tenho nenhum interesse em pessoas"* (para **essa** campanha) | `prompter.py:26-28` ROLES.mood "NO product, NO people, NO text, NO logos"; `prompter.py:152` `MOOD_GUARDS` força os três em todo prompt (`service.py:140`); template `service.py:68`; `view.html:4` "sem produto e sem pessoas (aula 009)"; `hld.md:11`; `prompter-fdd.md:58` | **alta** | Remover "no product/no logos/no text" dos guards e do papel do bot. Manter "no people" como **padrão sugerido** (checkbox marcado, texto "a aula não quis pessoas porque o foco é o produto"), nunca como injeção silenciosa. Corrigir a atribuição "(aula 009)" na tela, HLD e FDD; se quiser manter "sem produto" como opção, marcar `[extensão]` |
| M2 | desvio de processo | Referência de imagem da 2ª rodada é **a melhor imagem do 1º grid** como *style reference*; a 1ª rodada usa a **imagem de vibe** do Explore | `router.py:147` + `service.py:187-189`: CLI manda `refs/brainstorming/*.jpg` (Pinterest) como `image_references`; imagens de `mood/vibe/` e de `mood/candidates` **não** são usadas na geração | média | `use_refs` deve apontar para as imagens de vibe escolhidas (`vibeSel`) e, numa 2ª rodada, para a(s) candidata(s) marcada(s) como "melhor do grid". Renomear o checkbox: "usar as imagens de vibe como referência de estilo" |
| M3 | falta | *"copiar o prompt dessa pessoa"* (Explore) é o ponto de partida do 1º grid | Nenhum campo para colar o prompt copiado; o modo `template` inventa um prompt; `instruction` é "instrução para o bot" | média | Adicionar campo "Prompt copiado do Explore/da imagem de vibe (opcional)"; no modo `images` passar como "base prompt to preserve"; no modo template, se preenchido, usar como prompt e só acrescentar a variação de estilização |
| M4 | desvio (leve) | *"não precisa ter a ver com esse tipo de campanha […] só precisa gostar do sentimento"* | `service.py:29-38,65` injeta termos e `alt` das referências do Pinterest no prompt de vibe | baixa | Retirar `_refs_summary` do prompt de mood (deixar só produto + vibe + imagens de vibe); manter os termos disponíveis para a etapa 3 |
| M5 | extensão não marcada | A aula usa o **mood board de imagens** como filtro; nunca extrai cores | `service.py:213-227,252-254` `palette.json` (6 hex) consumido no prompt da etapa 3 (`base/service.py:129`) | baixa | Marcar `palette.json` como `[extensão]` (derivado técnico); documentar que o artefato fiel é `mood/selected/` e que a paleta é auxiliar |
| M6 | ok / ferramenta | Moodboard do MJ ↔ *"usar o nano banana mesmo, com alguma imagem de referência"* (o próprio instrutor) | etapa 3 anexa até 3 de `mood/selected/` (`base/service.py:45`) | — | Registrar no painel: "o Studio usa as imagens do mood como referência no Nano Banana — alternativa mostrada na aula" |
| M7 | ok | *"quadro com quatro imagens"*; salva as 4 da 2ª rodada (+ as do 1º grid que gostou) | grid de 4 na UI hint; teto 8 (ADR-007) | — | — |
| M8 | ok | *"Stylization um pouco mais forte"* quando parecidas demais | `_STYLE_VARIANTS` + "Nova variação" (`view.html:46`) | — | Pequeno: `_STYLE_VARIANTS` está duplicado em `mood/service.py:43` e `prompter.py:121` |
| M9 | ok (bot) | modos simplificado/guiado (007) e com imagem (009); *"ChatGPT normal também dá certo"* | `prompter.from_brief`/`from_images`; fallback template | — | — |
| M10 | texto da tela | aula não fixa proporção nem "2K" | `service.py:70-73` "Nano Banana Pro · 2K · 16:9 · … (ilimitado no Ultra)" | baixa | "2K/16:9" são escolhas do Studio; escrever "sugestão"; plano da aula 006 chama-se **Ultimate**, não "Ultra" |
| M11 | falta (menor) | Mood board de **filme** para realismo; pack no nível 2 | sem suporte a "mood de filme" | baixa | Mencionar no painel como técnica manual (imagens de filme em `mood/vibe/`); não implementar sem aprovação |

### 2.4 Texto sugerido para o painel-guia

**O que fazer nesta etapa**
Referências soltas geram uma campanha incoerente; ela precisa de **um** mood. Ache uma imagem cujo **sentimento** você gosta — não precisa ter a ver com o produto (a aula usou "snow neon commercial" no Explore). Copie o prompt dela ou peça ao bot um prompt com essa vibe (anexe a imagem de vibe e, se quiser, uma referência que você gostou; a aula pediu "sem pessoas" porque o foco é o produto). Gere um grid de 4; se saírem parecidas demais, aumente a estilização; se não pegou a vibe, pegue a melhor imagem como referência de estilo e gere mais 4 com o mesmo prompt. Salve as que estão no mesmo mood: esse conjunto vira o filtro de tudo o que você gerar daqui em diante.

**Checklist de qualidade da aula**
- Escolhi a vibe pelo sentimento, não pelo assunto
- Um único prompt de vibe (variações só de estilização)
- Evitei imagens focadas em rosto/pessoas — o produto é o foco
- O grid "pegou a vibe"? Se não, referência de estilo + mesmo prompt de novo
- Todas as imagens salvas estão no **mesmo** mood
- (Opcional, aula 004/009) mood board de filme para ganhar realismo

**Entradas necessárias:** 1 imagem de vibe (Explore/Pinterest/frame de filme); produto do projeto; opcional: prompt copiado do Explore.
**Saída esperada:** `mood/selected/` com 4–8 imagens no mesmo mood; `mood/mood.md` com o prompt de vibe; (`palette.json` é auxiliar `[extensão]`).

### 2.5 Validações automáticas possíveis

| Regra | Fonte |
|---|---|
| `mood/selected/` tem entre 1 e 8 imagens (422 acima de 8 já existe) | aula: 1 grid de 4, "todas elas"; ADR-007 |
| `mood/mood.md` registra **um** prompt de vibe (contar linhas "prompt:" distintas ≤ 2 — original + variação de estilo) | CLAUDE.md gate; aula |
| Prompt de vibe em inglês (heurística: ≥ 90 % ASCII, sem stopwords pt "com/para/uma") | aula 007 |
| Se `mode=images`, ≥ 1 imagem de vibe anexada | aula 009 |
| Prompt de vibe **não** contém "no product"/"no logos" injetado sem o usuário pedir (inverter o teste atual `test_mood_prompt_is_single_vibe_without_product`) | M1 |
| Imagens escolhidas têm paleta dominante próxima entre si (distância média dos 3 tons principais < limiar) — **aviso** "parecem moods diferentes" | aula: "todas no mesmo mood" |

---

## Etapa 3 — Imagem base (`base`)

### 3.1 O que a aula ensina (009, transcrição)

1. **Contexto para o bot:** *"vou tirar um print aqui de todas essas imagens [do mood] para ele entender o mood da minha campanha. […] Esta é a vibe da minha campanha."*
2. **Instrução ao bot (uma vez, vale para várias refs):** *"vou te apresentar algumas imagens. E o seu papel será […] criar um prompt de uma lata de energético na exata mesma situação da imagem de referência. Porém, com a vibe adaptada para a minha campanha. Pode começar com essa lata gigante."*
3. **Gerar com o mood board ligado** (demonstra sem/com: sem → *"muito estranha"*; com → *"bem mais próximo"*). Grid de 4 por prompt.
4. **Se o prompt não entregou (lata não ficou gigante) → nova aba do GPT, sem viés:** *"vou criar uma outra aba do meu GPT. E eu vou entregar essa referência para ele sem que ele saiba nada sobre a minha campanha. Para que ele não tenha nenhum tipo de viés. […] Crie o prompt de uma imagem idêntica a esta. Porém, o energético gigante está em uma montanha coberta de neve."* → *"prompt bem detalhado. Até o tipo de câmera."*
5. **Iterar por referência:** *"Faça a mesma coisa. Porém, dessa vez, a lata está nesta situação."*; *"você vai fazendo isso com as imagens de referência que você gostou, até que você encontre uma boa."*
6. **Ignorar marca/texto nas gerações:** *"Ignore os escritos. Não importa a marca que está saindo aqui na lata."*
7. **Escolher:** *"Aí é a questão de escolher, né? […] Então essa é a imagem base da minha campanha."* Salva em `imagens/` **fora** de brainstorming: *"imagem base da campanha"*. Ideias já nascem aqui (*"um mini ser humano em perspectiva"*).
8. **Trocar o rótulo (Higgsfield, Nano Banana):** arrasta a imagem; 1ª tentativa *"Troque o rótulo da lata por algo mais simples […] logomarca no formato de raio com efeito neon"* (3 variações) → *"ficou simples demais"* → reescreve: *"Troque o rótulo da lata. Mantenha as cores da lata, mas adicione uma logomarca no formato de raio com efeito neon."* Regra: *"esperar. É ter paciência."*
9. **Upscale:** *"Open in. Upscale. […] 2x. Faça exatamente como eu estou fazendo. […] preset High Fidelity V2"* → *"a mesma imagem, com uma qualidade um pouco maior."*
10. **Dever de casa:** postar a imagem base + prompt (ou o mood board completo) na aba de compartilhamento de prompts da comunidade.

### 3.2 O que a implementação faz

- `GET …/base/prompts` (`base/service.py:154-181`): exige ≥ 1 ref em `brainstorming/` e `palette.json` não vazio; devolve por referência um **template fixo** `situation_prompt` ("The product (X) in the exact same situation as the reference image, with the campaign mood: {note}, palette #…") e `prompt_no_bias` ("Write the prompt for an image identical to this one, but the X is the subject"); `label_prompt` a partir de `brand.json` (`[extensão]` marcada em código, tela e FDD); `upscale_hint`.
- `ui_hint` (`service.py:168-170`): "Abra uma aba nova na Higgsfield (sem histórico), anexe a referência e 1 a 3 imagens do mood, e cole o prompt."
- Importação com `kind ∈ {situation,label,upscale}` + `ref_id`; o prompt de origem herdado (`view.js:8-13`).
- `select` exclusivo por `kind`; `base_final.png` = mais avançada (`upscale > label > situation`); `base.md` com a cadeia. Reselecionar passo anterior derruba os seguintes.
- CLI: `_plan` (`service.py:342-372`) — situação: `nano_banana_2` com `[ref.jpg, até 3 mood]`; rótulo: `image_references=[situação]`; upscale: `bytedance_image_upscale`. `cost` + `confirm()`.
- Textareas dos prompts são `readonly` (`view.js:28`).
- `common/prompter.py` tem `ROLES["base"]` (`prompter.py:31-36`) mas `base/service.py` **não importa `prompter`** (imports em `service.py:26-29`); `prompter-fdd.md:17` adia isso "fora deste FDD".

### 3.3 Divergências

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção |
|---|---|---|---|---|---|
| B1 | **desvio de processo (falta)** | O prompt de situação nasce do **bot olhando a referência + print do mood**: *"o seu papel será criar um prompt de uma lata […] na exata mesma situação da imagem de referência"* → *"prompt bem detalhado. Até o tipo de câmera"* | `service.py:134-136` template de 2 frases, determinístico (`base-fdd.md:61-63` exige igualdade); `prompter` não é usado; `ROLES["base"]` (`prompter.py:31-36`) órfão | **alta** | Na etapa 3, "Gerar prompt" deve chamar `prompter.from_images("base", [ref] + mood/selected[:4], instruction)` por referência, com os mesmos 3 modos da etapa 2; manter o template atual só como fallback sem Claude. Ajustar o critério de determinismo do FDD (vale para o fallback) |
| B2 | **texto da tela enganoso** | A "aba nova sem viés" é do **GPT**: *"vou criar uma outra aba do meu GPT […] sem que ele saiba nada sobre a minha campanha"* | `service.py:168-170` ui_hint "Abra uma aba nova na Higgsfield (sem histórico) […] cole o prompt"; `view.js:40` rótulo "sem viés (aba nova)" ao lado de um texto que é **instrução para o bot**, não prompt de imagem | **alta** | Separar claramente: (a) "instrução para o bot (sessão nova, sem contexto)" → botão que roda `prompter.from_images` **sem** o brief do projeto; (b) "prompt para gerar" (saída do bot) → copiar para a Higgsfield com referência + mood anexados |
| B3 | desvio (menor) | Mood entra como **imagens** (print) | `service.py:129` põe hex da paleta no texto; `prompts()` aceita `mood_files=[]` (só avisa em `view.js:38`) | média | Exigir ≥ 1 imagem em `mood/selected/` (422 "volte à etapa 2 e salve o mood") como já se faz com a paleta; hex opcional |
| B4 | desvio (iteração) | Instrução de rótulo é **reescrita** quando o resultado não agrada ("simples demais"); 3 variações | `view.js:28` textarea `readonly`; `label_prompt` fixo; `count` default 1 (`router.py:43`) | média | Tornar os prompts editáveis (o import já herda o texto editado); default `count=3` para rótulo; guardar a instrução usada em `base.md` |
| B5 | falta (orientação) | *"Ignore os escritos. Não importa a marca que está saindo"*; *"até que você encontre uma boa"*; *"É ter paciência"* | Sem menção na tela | baixa | Incluir no painel-guia/checklist |
| B6 | falta (validação) | *"2x […] High Fidelity V2. Faça exatamente como eu estou fazendo."* | `upscale_hint` só texto; nada confere dimensão | baixa-média | Ao importar `kind=upscale`, comparar `width` com a candidata de origem: aviso se < 1,8× ou > 2,2× ("a aula pede 2x") |
| B7 | ok / ferramenta | Upscale na UI Higgsfield/MJ | `bytedance_image_upscale` via CLI + UI; ID não confirmado (`service.py:38-42`) | — | Validar ID com `model list` (pendência já registrada) |
| B8 | ok (extensão marcada) | Marca inventada na hora ("Abrahub", raio neon) | `brand` `[extensão]` em código (`service.py:13`, `:290`), tela (`view.html:27`) e FDD | — | — |
| B9 | ok | Pasta `imagens/` fora de `brainstorming` para a imagem base | `base/base_final.png` (nome diferente, mesmo papel) | — | ver §5 |
| B10 | falta (fora da ferramenta) | Dever de casa: postar imagem base + prompt na comunidade | — | baixa | Item final do checklist com o prompt de origem pronto para copiar (já está em `base.md`) |
| B11 | texto (menor) | "No people" na aula é do **mood**; na base ele até imagina "mini ser humano em perspectiva" | `service.py:46` `NO_PEOPLE` em todo prompt de situação e no "sem viés" | baixa | Manter como frase opcional (checkbox) em vez de fixa; FDD `base-fdd.md:188-189` já reconhece que é auto-aceite |

### 3.4 Texto sugerido para o painel-guia

**O que fazer nesta etapa**
Mostre ao bot o mood da campanha (as imagens da etapa 2) e, para cada referência que você gostou, peça "o prompt do meu produto na exata mesma situação desta imagem, com a vibe da minha campanha". Gere com o mood anexado (4 por prompt) e ignore a marca/os textos que saírem na embalagem. Se o resultado não entregou a ideia (ex.: a lata não ficou gigante), abra uma sessão nova do bot sem nenhum contexto e peça "o prompt de uma imagem idêntica a esta, porém …". Repita com as referências até achar uma boa e escolha a imagem base. Depois troque o rótulo pela sua marca no Nano Banana com uma instrução só ("troque o rótulo, mantenha as cores, adicione a logo …"), reescrevendo a instrução se ficar simples demais; por fim faça upscale 2x, preset High Fidelity V2.

**Checklist de qualidade da aula**
- O bot viu o mood **e** a referência antes de escrever o prompt
- Gerei com o mood anexado (sem ele "sai coisa muito estranha")
- Ignorei marca/texto errados na embalagem — o rótulo vem depois
- Tentei a "aba nova sem viés" quando o prompt não entregou a ideia
- Escolhi **uma** imagem base; já anotei as ideias que surgiram
- Rótulo: uma instrução por vez, mantendo as cores; iterei a instrução se precisou
- Upscale 2x, High Fidelity V2 (a mesma imagem, só com mais qualidade)
- Postei imagem base + prompt na comunidade (dever de casa)

**Entradas necessárias:** ≥ 1 referência em `refs/brainstorming/`; imagens em `mood/selected/`; produto; nome/descrição da marca (`[extensão]`, só para o passo do rótulo).
**Saída esperada:** `base/base_final.png` (com rótulo próprio e upscale 2x) + `base/base.md` com a cadeia situação → rótulo → upscale e os prompts/instruções usados.

### 3.5 Validações automáticas possíveis

| Regra | Fonte |
|---|---|
| `base/base_final.png` existe e é PNG válido; `chain.situation` preenchido | aula: "essa é a imagem base" |
| `chain.upscale` preenchido **e** `width(upscale) ≈ 2 × width(origem)` (±10 %) — senão aviso "falta o upscale 2x" | aula: "2x … High Fidelity V2" |
| `chain.label` preenchido quando `brand.name` existe — aviso "rótulo ainda é o da referência" | aula: "não quero propaganda de Red Bull" |
| `mood/selected/` ≥ 1 antes de liberar prompts | aula: print do mood para o bot |
| Prompt de situação em inglês e com ≥ 40 palavras (sinal de que veio do bot, "até o tipo de câmera") | aula 007/009 |
| Cada candidata `situation` tem `ref_id` de uma ref `selected` | invariante FDD |
| `base_final.png` ≥ 2048 px no lado maior (aviso, dado que Nano Banana 2K + 2x ≈ 4K) | [inferência] |
| `base.md` contém a instrução de rótulo usada e o prompt de situação | aula: dever de casa pede o prompt |

---

## 4. Regras gerais das aulas 005–008 × `config.py`, shell e etapas

### 4.1 O que as aulas dizem

- **005 — Mentalidade:** *"Não fique preso às plataformas. Fique preso ao processo."*; *"A ferramenta pode mudar, a interface pode mudar, o nome pode mudar, mas o processo […] continua."*; inserções de atualização no meio das aulas.
- **006 — Setup:** Midjourney (Standard) + Higgsfield **Ultimate** (~US$ 30/mês anual; *"Nano Banana Pro […] ilimitado"*); inserção: equipe **cancelou o Midjourney**, *"dá para você utilizar só o Higgsfield tranquilamente"*; custo = *"custo básico da sua empresa […] one-person business"*.
- **007 — Prompt:** *"Se você coloca intenção […] mood, ângulo de câmera, qual é a câmera, estilo"*; *"nada ao extremo é bom. Ela sempre alucina quando você coloca extremos"* (Stylization/Weirdness no meio); bot em modo simplificado (propósito, tom, referência em uma frase) ou guiado (passo a passo); **prompt em inglês** (*"língua nativa a qual elas são treinadas"*); formatos: vertical para Instagram/TikTok, quadrado para feed, wide para YouTube; *"tenta manter sempre o modelo mais novo"*; edição/retexture/expand; mood boards de filme trazem realismo.
- **008 — Plataformas:** *"plataforma nenhuma gera vídeo. O que gera os vídeos são os modelos"*; comparar **velocidade, estabilidade e custo**; modelos atuais: Seedance 2.0, Kling 3.0, Omni Flash; *"não vale a pena […] plano gratuito"*; nesta inserção **desaconselha Higgsfield** (marketing "ilimitado com letras miúdas", fim da fila) e recomenda **OpenArt** (cupom); *"a gente vai usar geração de vídeo comum que é o que dá o resultado de verdade."*
- **009 — Organização:** `campanha/` → `imagens/` (→ `brainstorming/` → `mood/`), `vídeos/`; imagem base em `imagens/`.

### 4.2 Divergências

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção |
|---|---|---|---|---|---|
| G1 | texto enganoso (comentário) | Aula 009: `imagens/brainstorming/mood`, `imagens/<base>`, `vídeos/` | `config.py:14` "espelha a organização da aula 009/011"; `PROJECT_LAYOUT` cria `refs/candidates`, `refs/brainstorming`, `mood`, `assets`, `images`, `videos`, `audio`, `edit`, `export`, `jobs`; etapas 1–3 gravam em `refs/`, `mood/`, `base/` e **nunca** em `images/` | baixa-média | Reescrever o comentário: "inspirado na aula 009 (brainstorming/mood/imagem base/vídeos); `candidates`, `assets`, `jobs`, `edit`, `export` são infraestrutura do Studio `[extensão]`". Ou mapear literalmente: `images/brainstorming`, `images/mood`, `images/base` |
| G2 | desvio de ordem | 009: *"Você não precisa ter ideia nenhuma ainda"*; a vibe é achada na etapa 2 | `index.html:21-23` pede `vibe` na criação; `mood/service.py:59` usa `vibe` no prompt | baixa-média | `vibe` opcional e rotulado "(será definido na etapa 2)"; etapa 2 grava `project.vibe` a partir da `note` do `select` |
| G3 | desvio (formato) | 007: escolher formato pelo destino (vertical IG/TikTok, wide YouTube) | `mood/service.py:73`, `base/service.py:170` fixam `16:9` sem campo de projeto | baixa-média | Campo `aspect_ratio` no projeto (default 16:9) propagado às etapas; texto "a aula manda escolher pelo destino" |
| G4 | ok (gate 3) | 008: plataforma é agregador; 006: Higgsfield só basta; 008: OpenArt recomendada | ADR-002 Higgsfield-somente via CLI; `model` sobrescritível em todas as rotas | — | Registrar no painel inicial que a escolha da Higgsfield é decisão do Studio (aula 008 recomenda OpenArt); a abstração por **modelo** honra a tese da aula |
| G5 | ok | 008: custo é o principal critério; 006: ilimitado só na UI | `cost` + `confirm()` antes de gerar; "ilimitado da UI não vale no CLI" nas telas | — | — |
| G6 | ok | 007: prompts em inglês | prompter e templates em inglês; CLAUDE.md "Idioma" | — | Adicionar validação heurística (ver §2.5) |
| G7 | ok | 007: "intenção" = mood + ângulo + câmera + estilo | `ROLES.*` pedem câmera/lente/abertura/luz | — | — |
| G8 | falta (menor) | 007: "nada ao extremo" | Sem indicação de Stylization/weirdness moderado no ui_hint | baixa | Uma linha no painel da etapa 2: "estilização no meio-termo; extremos alucinam" |
| G9 | ok | 005: processo > plataforma; inserções | Shell mostra "aula NNN" por etapa (`app.js:70`); modo UI + CLI | — | Painel-guia por etapa (pedido deste relatório) fecha a lacuna de orientação |
| G10 | texto (menor) | 006: plano **Ultimate** | `mood/service.py:70,105`, `view.html:35`, `base/view.html:12` "Ultra" | baixa | Trocar por "Ultimate" |

### 4.3 Texto sugerido para o painel inicial (shell)

**Como o Studio segue o curso**
Cada etapa reproduz uma aula (o número aparece ao lado). A regra do instrutor é "fique preso ao processo, não à plataforma": aqui o Midjourney/Higgsfield UI viram Higgsfield (UI ilimitada + CLI pago) e o bot da comunidade vira o Claude local; o processo, as entradas e as saídas são os da aula. Prompts de imagem em inglês, com intenção (mood, ângulo, câmera, estilo). Antes de gastar créditos o Studio mostra o custo — na aula 008 o custo é o principal critério.

---

## 5. Validações transversais (todas as etapas)

| Regra | Fonte |
|---|---|
| Ordem obrigatória: etapa N só libera com a saída da N-1 (`refs/brainstorming` → `mood/selected` → `base_final.png`) | aula 009 (sequência) |
| Todo prompt gravado (`mood.md`, `base.md`, `prompts.json`) em inglês | aula 007 |
| Cada artefato de etapa registra o prompt/instrução de origem | aula 009 (dever de casa pede o prompt) |
| Toda extensão aparece com `[extensão]` em código, tela e doc — hoje só `brand` cumpre; `palette.json`, "por quê" do README, `vibe` no projeto, `refs/candidates` não | CLAUDE.md gate 2 |
| Nenhum texto de tela atribui à "aula 009" regra que a transcrição não contém (M1, B2, R3) | CLAUDE.md gate 1 |

---

## 6. Prioridade de correção

1. **M1** — remover "no product/no text/no logos" forçado no mood; corrigir atribuição "(aula 009)" em `view.html`, `hld.md`, `prompter-fdd.md`, teste `test_mood_prompt_is_single_vibe_without_product`.
2. **B1 + B2** — etapa 3 usar o `prompter` (ROLES["base"]) com referência + mood; separar "instrução ao bot (sessão sem viés)" de "prompt para gerar"; corrigir ui_hint "aba nova na Higgsfield".
3. **M2** — geração via CLI do mood com imagens de vibe/grid como referência, não com `refs/brainstorming`.
4. **B4, B3** — prompts editáveis, `count=3` no rótulo, exigir `mood/selected/`.
5. **R1, M3, G2, G3** — campo de marca validada; campo para prompt copiado do Explore; `vibe` e `aspect_ratio` no lugar certo.
6. **G1, R4, M5, G10** — comentários e marcações `[extensão]`; "Ultimate".

Arquivos-chave citados: `/home/arthu/code/senhortecnologia/orquestrador-studio/studio/{config.py, refs/service.py, mood/service.py, common/prompter.py, base/service.py}`, `studio/etapas/{refs,mood,base}/{router.py,view.html,view.js}`, `studio/web/{index.html,app.js}`, `docs/domains/{refs/hld.md, mood/hld.md, mood/features/prompter-fdd.md, base/features/base-fdd.md}`; transcrições em `/home/arthu/code/senhortecnologia/aprendizado/20260824-162323/01-curso-iniciante-o-orquestrador/media/00X--*.txt`.
