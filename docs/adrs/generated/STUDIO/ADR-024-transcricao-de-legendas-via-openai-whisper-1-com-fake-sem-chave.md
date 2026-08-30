# ADR-024: Transcrição de legendas via OpenAI `whisper-1`, com fake sem chave `[extensão]`

**Status:** Aceito
**Data:** 2026-08-29
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260829-39
**ADRs relacionados:** [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-030](./ADR-030-editor-de-video-completo-como-extensao-nao-destrutiva-da-etapa-8.md)

## Contexto e Problema

O editor de vídeo completo da etapa 7 (ADR-030) já tem a faixa de legenda (`t_cap`) e o burn-in
de texto no `master.mp4`, mas o botão "Gerar" só mostrava um toast: **não havia transcrição no
projeto**. O próprio FDD do editor registrou a pendência — "geração de legenda automática
(depende de transcrição — não há no projeto hoje)". Sem ela, o usuário digita legenda a legenda e
não tem como sincronizar com a fala.

Legenda automática é `[extensão]` aprovada explicitamente pelo dono do produto (ADR-004,
CLAUDE.md regras 2 e 4): **a aula 014 monta no CapCut sem legendas**. O backbone da aula (clipes,
pretos, música, SFX, fade, loudnorm) não muda; a legenda entra por cima, opcional.

O problema arquitetural é que sincronizar palavra com fala exige **tempo por palavra**, e isso
significa transcrição. O studio não tinha nenhum caminho para isso:

- **É o primeiro serviço externo HTTP do studio.** Até aqui, tudo que sai da máquina sai por
  subprocess: o CLI oficial da Higgsfield (ADR-002) e o scraping do Pinterest via Playwright
  (ADR-005). Nenhum módulo abre uma conexão HTTP para uma API de terceiro.
- **A ADR-002 restringe apenas a Higgsfield.** Ela proíbe falar com `api.higgsfield.ai` direto ou
  automatizar a UI da Higgsfield — a ponte continua sendo o CLI oficial, e esta decisão não a
  toca. Não há conflito: o whisper não é a Higgsfield, e nada aqui abre um segundo caminho para
  ela.
- **A ADR-008 exige suíte sem rede.** Nenhum teste pode abrir socket. Um provedor externo obrigatório
  quebraria a estratégia de testes e o CI.
- **Não há `OPENAI_API_KEY` no ambiente desta entrega.** O provedor precisa ser opcional de
  verdade: o app é local, single-user, e tem de funcionar inteiro sem chave nenhuma.

Somado a isso, há uma lição de regressão já documentada (§10 do FDD desta frente): aceitar o texto
que o whisper devolve como legenda produz o efeito "gaélico" — palavra trocada, idioma errado,
contagem diferente do roteiro. O texto que aparece na tela não pode ser o texto ouvido quando o
usuário já nos deu o roteiro.

## Decisão

**Transcrever com o modelo `whisper-1` da OpenAI, pelo SDK oficial `openai`, com import lazy e um
fake determinístico como comportamento padrão sem chave.** Concretamente:

1. **SDK `openai>=1.40`, import lazy.** A dependência entra só em `requirements.txt` (única lista
   de deps do repo) e o `import openai` acontece **dentro do método** que chama a API, nunca no
   topo do módulo. `import studio.edit.captions` não traz `openai` para `sys.modules`.

2. **Modelo e parâmetros fixos.** `client.audio.transcriptions.create(model="whisper-1",
   response_format="verbose_json", timestamp_granularities=["word"], language="pt")`. O
   `verbose_json` por palavra é o que dá o tempo de cada palavra; `language="pt"` fixo elimina a
   principal fonte do "gaélico" (o whisper adivinhando idioma em áudio curto ou ruidoso).

3. **Chave lida em runtime.** `get_transcribe()` lê `OPENAI_API_KEY` **na hora da chamada**, não
   na importação do módulo: exportar a chave e recarregar a página basta, sem reiniciar o app.
   Com chave → `OpenAITranscribe`; sem chave → `FakeTranscribe`.

4. **`FakeTranscribe` é o caminho padrão, não um mock de teste.** Sem chave, o app responde
   `source:"estimate"` com tempos proporcionais determinísticos (2,4 palavras por segundo, peso
   `len+1` por palavra). O usuário sem chave tem legenda funcionando — só não sincronizada com o
   áudio. É também o que a suíte exercita (ADR-008): nenhum teste faz rede, jamais, e o SDK real,
   quando precisa ser exercitado, é falsificado em `sys.modules["openai"]`.

5. **Política assimétrica de falha.** As duas chamadas do provedor tratam erro de formas opostas,
   e isso é intencional:
   - `words(audio, text, duration)` — **temos o texto**. Falha do provedor cai em `proportional`
     e a requisição responde `200` com `source:"estimate"` e um campo `warning`. Legenda é
     enfeite: o texto continua certo, só perde a sincronia.
   - `transcribe_text(audio, duration)` — **não temos o texto**. Falha levanta `ProviderError`,
     que o router traduz em **502**. Cair em estimativa aqui significaria pôr na tela um texto
     que ninguém escreveu; é melhor falhar explicitamente.

6. **"Nosso texto, tempo ouvido".** Quando o usuário manda o roteiro junto com o áudio, o texto
   exibido é **sempre** o dele; a transcrição só fornece o tempo (`align`). Invariante verificada
   em teste: `[w.w for w in words] == text.split()`. Quando a contagem ouvida diverge da nossa, as
   palavras são distribuídas proporcionalmente dentro do intervalo real da fala. O texto do
   whisper só vira legenda no caso em que não existe outro texto (`source=audio` sem `text`).

7. **Síncrono, com timeout curto.** `OpenAI(api_key=…, timeout=120, max_retries=1)` — o SDK usa 2
   retries por default, e 1 mantém o pior caso em ~4 min. Sem backoff próprio e sem circuit
   breaker: é um app local single-user. O áudio é recortado por `duration` e barrado em 25 MB
   (teto do whisper) antes de sair da máquina.

## Alternativas Consideradas

1. **Whisper local (`openai-whisper` / `faster-whisper`)** — sem rede, sem custo, sem chave. Custa
   o peso do modelo (centenas de MB a baixar na primeira execução) e CPU pesada numa máquina que
   já está editando vídeo com ffmpeg: a transcrição competiria com o render pelo mesmo processador.
   Para um app local que roda ao lado do editor, é o tipo de dependência que transforma "gerar
   legenda" numa espera de minutos. Continua sendo o plano B mais óbvio se a chamada paga incomodar.

2. **Transcrever no browser (Web Speech API / whisper em WASM)** — tiraria a decisão do servidor e
   quebraria duas regras de uma vez: a ADR-008 (a suíte do servidor não conseguiria testar o
   caminho, que passaria a viver só no `view.js`) e o desenho desta frente, em que **o servidor
   decide as janelas** e o front só as re-fatia por `chunk`. Além disso a qualidade em português é
   irregular e varia por navegador.

3. **Aceitar o texto do whisper como a legenda, sempre** — mais simples: uma chamada, um texto,
   pronto. É exatamente a regressão do "gaélico" documentada na §10 do FDD: palavra trocada,
   idioma errado ou contagem diferente do roteiro viram legenda errada na tela do usuário, com o
   agravante de parecer certa. Rejeitada: quando temos o roteiro, ele é a fonte do texto.

4. **Não ter legenda automática** — manter a pendência da ADR-030 aberta e deixar tudo manual.
   Rejeitada porque o dono aprovou a extensão explicitamente e a digitação legenda a legenda é o
   trabalho que o editor existe para eliminar.

## Consequências

**Positivas**

- A pendência "geração de legenda automática" da ADR-030 fecha na parte servidor, sem tocar no
  backbone da aula 014 e sem persistir nada de novo (o `generate` devolve os itens na resposta;
  quem grava é o `PUT /timeline` que já existia — ADR-003).
- O app continua **inteiramente funcional sem chave e sem rede**: `FakeTranscribe` +
  `proportional` cobrem o caminho padrão, e o resultado é determinístico.
- A suíte segue **100 % fake** (ADR-008): nenhum teste importa `openai` de verdade nem abre socket;
  o SDK é falsificado em `sys.modules` quando o caminho real precisa ser exercitado.
- A ADR-002 permanece intacta: a ponte com a Higgsfield continua sendo só o CLI oficial.

**Negativas / custos**

- **Dependência de rede opcional, mas nova.** O studio passa a ter um caminho HTTP para fora que
  não é subprocess. Com chave configurada, `generate` por áudio depende da OpenAI estar de pé; sem
  chave, nada muda.
- **Custo não contabilizado no livro-caixa (ADR-016).** Esta entrega **não** registra o gasto do
  whisper em `record_generation` nem no painel de créditos: o contrato congelado da frente não fala
  em créditos e a decisão foi deixar a integração para uma rodada seguinte. É uma **lacuna
  intencional e registrada aqui**: o gasto existe (por minuto de áudio) e hoje só aparece no log
  da chamada, com `elapsed_ms` e o `word_count`. Fechar a lacuna é adicionar
  `record_generation("edit.captions")` no serviço.
- **O provedor real não foi exercitado nesta entrega.** Não há `OPENAI_API_KEY` neste ambiente:
  `OpenAITranscribe` foi implementado conforme a especificação e validado apenas contra um SDK
  falso injetado em `sys.modules`, nunca contra a API da OpenAI. A primeira execução com chave real
  é, por definição, a primeira validação de ponta a ponta.
- **Chamada síncrona.** A requisição fica presa até 120 s no pior caso, sem progresso na UI. Se o
  tempo medido incomodar, o plano B é mover a transcrição para o `JobRegistry` com polling
  (ADR-006), sem mudar o shape da resposta final.
- A chave nunca aparece em log, resposta ou arquivo; o texto do roteiro aparece nos logs apenas
  como `word_count`.
