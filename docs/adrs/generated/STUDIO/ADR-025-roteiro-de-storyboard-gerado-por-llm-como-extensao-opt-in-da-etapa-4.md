# ADR-025: Roteiro de storyboard gerado por LLM como extensão opt-in da etapa 4 `[extensão]`

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-03
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-018](./ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md), [ADR-022](./ADR-022-video-por-foto-no-storyboard-modelo-selecionavel-e-ponte-para-o-downstream.md)

## Contexto e Problema

A aula 010 manda o ALUNO escrever a história em ~5 cenas ("cena 1: close no astronauta andando na
nevasca..."). O Studio reproduziu isso literalmente: `storyboard/scenes.json` nasce com 5 cenas
vazias e a tela só oferece o momento do arco como dica (`SCENE_ARC`: começo → descoberta → ação →
desfecho). A docstring do módulo da etapa dizia, em letras claras:

> O que a aula não ensina fica de fora: **nada de roteiro por LLM**, shotlist ou ângulos por cena
> nesta mesma etapa.

Esse texto não é decoração: é a materialização do ADR-004 (fidelidade ao roteiro do curso como
restrição arquitetural) no arquivo mais tentador do repositório para inventar método.

O levantamento do curso feito na abertura da Wave 9 encontrou, mesmo assim, uma lacuna real: quem
trava na escrita fica parado na etapa 4 **tendo em mãos todo o insumo de que um roteiro precisa** —
a imagem base da etapa 3, o mood aplicado da etapa 2, o produto e a vibe do projeto e a proporção
da campanha. E, mesmo quem escreve as cenas sem dificuldade, ainda precisa inventar do zero o
prompt de imagem de cada uma, sem o rigor do "briefing de diretor de fotografia" que a Wave 9
acabara de codificar no catálogo de presets de realismo (feature irmã `prompter-presets-realismo`).

O dono do produto aprovou a extensão na abertura da wave e o gate W3 em lote a confirmou,
condicionando-a a esta ADR. O problema arquitetural a resolver não é "chamar um LLM" — o
precedente já existe (`video_prompt` usa `prompter.from_images("motion", ...)` desde a wave 7, pelo
mesmo Claude CLI local, grátis). O problema é **como oferecer roteiro automático sem que ele deixe
de ser sugestão**, isto é, sem que o caminho da aula deixe de ser o padrão e sem que uma tecla
errada apague o texto que o usuário escreveu à mão.

## Decisão

**Oferecer geração de roteiro completo por LLM como `[extensão]` estritamente opt-in, com a
sugestão isolada em arquivo próprio e a aplicação às cenas sob controle explícito do usuário.**
Concretamente:

1. **Papel novo no prompter, canal de sempre.** `prompter.ROLES["script"]` + `prompter.script(...)`
   geram, em uma chamada, N cenas com `text` em pt-BR (≤ 500 caracteres, o `MAX_SCENE_TEXT`
   vigente) e `image_prompt` em inglês no formato briefing de diretor de fotografia. O canal é o
   Claude CLI local — assinatura do usuário, **zero crédito Higgsfield**, mesmo caminho do
   `video_prompt`. `_parse`, `PROMPT_FORMAT`, `split_sections` e `provenance` ficam intocados: o
   roteiro tem `SCRIPT_OUTPUT_SPEC`, `_parse_script` e `script_preset_block` próprios, para não
   desestabilizar o prompt único de que a feature `base-prompt-provenance` depende. O timeout
   também é próprio (`SCRIPT_TIMEOUT_S = 300`, entre os 180 s do prompter e os 600 s dos jobs
   pagos): um roteiro de até 10 cenas com imagens demora mais que um prompt.

2. **A sugestão NÃO é a cena.** O roteiro é persistido em `storyboard/script.json` (`SCRIPT_FILE`),
   arquivo novo, ignorável por todo o resto do código e escrito com `write_json_atomic` apenas
   quando o job termina com resposta válida. **Nenhum caminho de código do servidor escreve em
   `storyboard/scenes.json`** — o schema da cena do ADR-018/022 fica intacto, sem um campo novo
   sequer, e o `image_prompt` por cena vive só no `script.json`.

3. **A aplicação é um gesto do usuário, e é assimétrica.** A sugestão chega às cenas pelo
   `PUT /api/projects/{pid}/storyboard/scenes` que já existia, disparado pela tela: "aplicar às
   cenas vazias" preenche apenas as cenas com `text` vazio, sem diálogo; "substituir tudo" exige
   confirmação explícita que diz **quantos** textos serão sobrescritos. A assimetria é
   deliberada — preencher vazio não destrói nada; sobrescrever destrói trabalho manual.

4. **Sem fallback determinístico.** Diferente do `video_prompt` (um prompt, template preenchível),
   um roteiro de N cenas exige conteúdo narrativo: um template determinístico só produziria N
   cenas iguais, ou seja, inventaria. Claude CLI ausente → **409** com mensagem que aponta o modo
   manual. O "fallback" desta feature é o método da aula, que continua sendo o caminho padrão.

5. **Preset de realismo com default ATIVO, por exceção.** A feature irmã fixou preset opt-in
   (default de código `null`) para `mood`, `base` e `motion`, para manter os prompts do curso
   byte-idênticos. O roteiro é o oposto: ele é `[extensão]` inteira, não tem prompt do curso a
   preservar, e a qualidade do `image_prompt` depende do rig. Por isso a ação `storyboard.script`
   nasce com default de código `documentary-street`, registrada em `settings.PRESET_ACTIONS` pelo
   próprio módulo da etapa (o dict é aberto de propósito), sem editar `settings.py`. A resolução
   segue o padrão ADR-016: projeto → global → código.

6. **Job assíncrono no padrão da casa.** `JobRegistry` próprio + polling (ADR-006), um roteiro por
   projeto. Sem `confirmCost`, porque não há custo — e, pela mesma razão, **sem
   `record_generation`**: o livro-caixa do ADR-016 é de créditos Higgsfield.
   Detalhe de implementação que vale registrar: o registry chama-se `_story_registry`, e não
   `_script_registry`, porque `studio/common/reset.py::_registries` descobre os registros de uma
   etapa por uma lista **fechada** de nomes de atributo (`_registry`, `registry`,
   `_story_registry`) — qualquer outro nome deixaria o job invisível para o reset da etapa.

7. **A docstring da etapa ganha ressalva, não reescrita.** O texto "nada de roteiro por LLM"
   permanece legível como registro do que a aula ensina, com uma nota `[extensão]` ao lado
   apontando para esta ADR. Um leitor futuro precisa enxergar as duas coisas: o que o curso manda
   e o que o produto decidiu acrescentar por cima.

## Consequências

**Positivas**

- A etapa 4 deixa de ser um beco para quem trava na escrita, sem que o método da aula perca o
  posto de caminho padrão.
- O `image_prompt` por cena nasce com o rig do preset de realismo aplicado, fechando o handoff da
  Wave 9 entre a feature provedora e esta consumidora.
- `scenes.json` intocado significa que animate (etapa 5) e todo o downstream continuam lendo o
  mesmo contrato; projetos antigos e projetos sem `script.json` funcionam idênticos.

**Negativas e riscos aceitos**

- **O repositório passa a conter um desvio explícito do texto da própria etapa.** É o custo
  registrado desta decisão, e a razão de esta ADR existir.
- A dependência opcional do Claude CLI cresce: antes só prompts, agora roteiro. Sem CLI, uma
  função visível da tela simplesmente não existe (409) — assumido.
- Qualidade da resposta do LLM é instável por natureza: JSON malformado ou cenas de menos derrubam
  o job em `state: "error"`, sem completar nada. É a escolha certa (não inventar), mas produz uma
  falha visível que o usuário resolve regerando.
- O default de preset ATIVO em `storyboard.script` é uma exceção à regra opt-in da feature irmã;
  quem ler só o ADR-016 pode estranhar. Por isso está escrito aqui.

**Neutras**

- Modelo alvo restrito a Nano Banana Pro na v1 (`SCRIPT_MODELS`, gate W3 P3): reversível e
  aditivo. `MODELS` (que tem o `gpt_image_2` `[extensão]`) continua servindo só ao caminho pago
  de ideação da mesma etapa.
- O guia da etapa (`guide.py`) não anuncia o roteiro nesta entrega — fora do escopo do FDD,
  registrado como sugestão ao dono.
- Duas asserções de igualdade EXATA em testes pré-existentes precisaram ser estendidas para
  acomodar os campos aditivos: o mapa `defaults` de `GET /api/prompter/presets` (que agora tem
  também `storyboard.script`) e o dict de `status` da etapa 4. Nenhum comportamento anterior
  mudou — só a régua dos testes deixou de ser "exatamente estas chaves".
