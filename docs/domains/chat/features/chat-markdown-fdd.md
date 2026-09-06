### FDD: chat-markdown `[extensão]`

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-03
Card(s): #85 https://trello.com/c/lqrj73sV
Wave: 11 (F01, sub-wave 1) · Recon compartilhado: `docs/domains/studio/recon-wave-11.md`

---

### 1. Contexto e motivação técnica

**Problema técnico.** As tools do MCP devolvem texto **em markdown** por construção
(`studio/mcp/tools.py:46` produz `Campanha **{name}** (\`{pid}\`)`, `:35-38` produz listas com
`- `), e o próprio agente escreve markdown porque é o formato natural de saída do CLI `claude`.
A bolha do assistente, porém, renderiza `{ev.text}` como **texto puro**
(`frontend/src/areas/chat/ChatDock.tsx:288-293`), com o único tratamento sendo
`white-space: pre-wrap` (`frontend/src/areas/chat/chat.css:100`). O resultado visível é
asterisco, crase e hífen literais na tela. Não há nenhuma biblioteca de markdown em
`frontend/package.json:18-22` (deps: `@tanstack/react-query`, `react`, `react-dom`).

**Encaixe no HLD.** O HLD de chat (`docs/domains/chat/hld.md`, v1.0, Onda A) descreve
`frontend/src/areas/chat/` como o dock lateral do shell (`ChatDock` + `useChatSocket` +
`chat.css`) e diz que cada linha do stream vira evento normalizado empurrado ao WS. Esta feature
acrescenta **um componente de apresentação** dentro dessa mesma área, sem tocar em runtime, em
protocolo de WebSocket, em rota REST nem em tool do MCP. O componente `MessageMarkdown` passa a
fazer parte da tabela de componentes do HLD de chat (a atualização do HLD é feita pela W5 via
`dd-parallel-doc-sync`, não por esta frente).

**Precedente documental.** `docs/plano/plano-chat-orquestrador.md:262` já previa
`MessageMarkdown.tsx` com `react-markdown` + `remark-gfm`, e `:331` já registrava o custo
estimado de bundle (~40 KB gz). A capacidade nunca foi implementada em nenhuma das Ondas A a E.

**Atores.** (a) o usuário do Studio, que lê a bolha; (b) o agente `claude -p`, que produz o
texto; (c) as tools do MCP, que produzem markdown determinístico; (d) o dock React, que
renderiza. Nenhum ator novo.

**Limites.** Frente exclusivamente de frontend. Zero mudança de backend, zero rota nova, zero
modelo Pydantic novo, portanto **sem `make frontend-schema`**. O núcleo tocado é `frontend/`
(inclusive `package.json`, que é núcleo por ADR-031) e o bundle versionado `studio/web/dist/`
(ADR-031, ADR-032). Chat e MCP são `[extensão]` do curso (ADR-036/037/038/040), logo esta feature
herda a marcação `[extensão]`.

#### Provides / Consumes (copiado de `docs/domains/studio/waves/wave-11.md`)

**Provides**
- Componente `frontend/src/areas/chat/MessageMarkdown.tsx` (react-markdown + remark-gfm, sem HTML
  cru, imagens só de `/files|/mbfiles|/cfiles`), usado em `assistant_text` e `tool_result` de erro.
- Estilos `.chat-bubble` para markdown em `chat.css` (dois temas).

**Consumes**: nenhum (candidata imediata, sub-wave 1).

---

### 2. Objetivos técnicos

- **Markdown renderizado como DOM semântico.** Dado `**Campanha X**` no texto de um
  `assistant_text`, o DOM contém um elemento `strong` com o conteúdo `Campanha X` e **nenhum**
  caractere `*` no `textContent` da bolha. Invariante: nenhum asterisco, crase ou hífen de lista
  literal sobra na bolha do assistente.
- **Superfície de injeção fechada por construção.** Nenhum HTML cru vindo do modelo vira
  elemento do DOM: `rehype-raw` não é instalado nem importado, e o teste afirma que um
  `<script>` no texto não produz elemento `script`. Invariante: o conjunto de tags que
  `MessageMarkdown` pode produzir é fechado e enumerado na seção 5.
- **Mídia só do próprio Studio.** Uma imagem markdown só vira `img` quando o `src` começa com
  `/files/`, `/mbfiles/` ou `/cfiles/` (os três mounts estáticos do `studio/app.py:216,218,220`).
  Invariante: zero requisição de rede para fora do loopback saindo da bolha (ADR-001).
- **Texto do usuário nunca passa pelo parser.** A bolha `user` continua renderizando `{ev.text}`
  cru com `white-space: pre-wrap`. Invariante verificável por teste: `**a**` digitado pelo
  usuário aparece com os asteriscos.
- **Custo de bundle conhecido e registrado.** O delta de `studio/web/dist/` medido antes e depois
  é registrado no corpo do PR; alvo de referência ~40 KB gz (`plano-chat-orquestrador.md:331`).
- **Tolerância a markdown incompleto.** Renderizar `**Camp` (marcação não fechada) não lança
  exceção e não desmonta o dock. Prepara o terreno para o `assistant_delta` do card #2 (F02).

---

### 3. Escopo e exclusões

**Incluído**
- Componente `frontend/src/areas/chat/MessageMarkdown.tsx` com `react-markdown` + `remark-gfm`,
  versões **pinadas** (sem `^`) em `frontend/package.json`.
- Uso do componente em exatamente **dois** pontos de `ChatDock.tsx`: o caso `assistant_text`
  (`:288-293`) e o ramo `is_error` do caso `tool_result` (`:297`).
- Override de `a` (nova aba com `rel="noopener noreferrer"`), de `img` (allowlist de prefixos) e
  de `pre` (bloco de código com `CopyButton` do design system, `frontend/src/ui/CopyButton.tsx`).
- Estilos de markdown em `chat.css`, escopados em `.chat-md`, usando **apenas tokens de tema já
  existentes** (`--ink`, `--ink-2`, `--ink-3`, `--line`, `--line-2`, `--surface`, `--surface-2`,
  `--bg-2`, `--accent`), o que dá os dois temas de graça (`frontend/src/styles/style.css:48-59`
  para `prefers-color-scheme: dark` e `:78-88` para `[data-theme="dark"]`).
- Remoção do `white-space: pre-wrap` da regra genérica `.chat-bubble` e sua reaplicação na regra
  específica da bolha do usuário.
- Testes Vitest novos em `frontend/src/areas/chat/MessageMarkdown.test.tsx`.
- Declaração de titularidade de núcleo em `tests/test_adr010_fronteira_nucleo.py`.
- `make frontend-verify`, `make frontend-build` e commit de `studio/web/dist/`.

**Excluído**
- Qualquer mudança em `studio/chat/`, `studio/mcp/`, `studio/app.py` ou nos prompts do sistema.
- Streaming/deltas de texto (`assistant_delta`), botão Parar, rótulos de tool: são de **F02
  chat-feedback** (card #86).
- Realce de sintaxe por linguagem (`rehype-highlight`, `shiki`, `prism`). Fica fora: custo de
  bundle desproporcional para uma ferramenta local que mostra sobretudo `pid` e nomes de arquivo
  em `code` inline.
- Renderização de markdown na bolha do **usuário**, no `chat-note` (`notify`), no
  `chat-tool` de sucesso e nos cartões `ask`/`show`. Ficam como estão.
- Lista virtualizada (`@tanstack/react-virtual`, previsto no plano §5 como opcional).
- Renderização de HTML cru, mesmo sanitizado (`rehype-raw` + `rehype-sanitize`).
- Renderização de imagens externas (http/https de fora do Studio).
- Atualização de `docs/domains/chat/hld.md`: é trabalho da W5 (`dd-parallel-doc-sync`); aqui só
  fica registrado que o componente entra na tabela de Componentes do HLD.
- Cenário Playwright de QA para o chat (`scripts/qa/cenarios/chat.py` não existe; a lacuna está
  registrada no recon §0.5 e continua registrada).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (único): evento do WS vira DOM formatado**

1. O `useChatSocket` entrega um evento normalizado ao `ChatDock`; o componente `Message`
   (`ChatDock.tsx:280`) despacha por `ev.kind`.
2. `kind === "assistant_text"`: a bolha passa a ser
   `<div className="chat-bubble" data-md="1"><MessageMarkdown text={ev.text ?? ""} /></div>`.
3. `MessageMarkdown` monta `<div className="chat-md">` e delega a `<Markdown remarkPlugins={[remarkGfm]}
   urlTransform={transformarUrl} components={COMPONENTES}>{texto}</Markdown>`.
4. O `react-markdown` parseia (remark) e converte para hast (rehype) **sem** `rehype-raw`, de modo
   que todo nó `html` do markdown é descartado antes de virar React.
5. Os overrides de `COMPONENTES` decidem o DOM final de `a`, `img` e `pre`; todo o resto usa o
   mapeamento padrão (`p`, `ul`, `ol`, `li`, `strong`, `em`, `code` inline, `blockquote`, `h1`
   a `h6`, `hr`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `del`).
6. O CSS de `.chat-md` em `chat.css` aplica tipografia e espaçamento com os tokens de tema; o
   navegador resolve claro/escuro pelas variáveis já definidas em `styles/style.css`.

**Fluxos alternativos e exceções**

- *Texto do usuário.* `kind === "user"` (`ChatDock.tsx:282-287`) permanece `{ev.text}`, sem
  `MessageMarkdown`. A regra CSS de `white-space: pre-wrap` migra de `.chat-bubble` para
  `.chat-msg.user .chat-bubble`, preservando as quebras de linha do que o usuário digitou.
- *Erro de tool.* `kind === "tool_result" && ev.is_error` (`ChatDock.tsx:297`) troca
  `{String(ev.content ?? "erro na ferramenta")}` por
  `<MessageMarkdown text={String(ev.content ?? "erro na ferramenta")} compact />`. A variante
  `compact` mantém a fonte monoespaçada e a cor de falha do `.chat-tool[data-err="1"]`
  (`chat.css:118`) e zera as margens de bloco.
- *Sucesso de tool.* Continua devolvendo `null` (comportamento atual preservado).
- *Link externo.* `[x](https://exemplo.com)` vira
  `<a href="https://exemplo.com" target="_blank" rel="noopener noreferrer">x</a>`.
- *Link com protocolo perigoso.* `[x](javascript:alert(1))` cai no `defaultUrlTransform` do
  próprio `react-markdown`, que zera o `href`; o resultado é um `a` sem destino navegável.
- *Imagem interna.* `![base](/files/pid/base/candidates/x.png)` vira
  `<img src="/files/…" alt="base" class="chat-md-img" loading="lazy">`.
- *Imagem externa.* `![x](https://exemplo.com/a.png)` **não** produz elemento algum (o override
  de `img` devolve `null`), conforme a proposta do card.
- *HTML cru.* `<b>oi</b>` produz o texto `oi` sem elemento `b`; `<script>alert(1)</script>`
  não produz elemento `script` nem executa nada. O nó `html` é descartado pelo pipeline.
- *Markdown incompleto.* `**Camp` (herança do futuro `assistant_delta` de F02) renderiza o texto
  literal `**Camp` como parágrafo, sem exceção. Nenhuma marcação parcial derruba o dock.
- *Bloco de código.* Uma cerca ```` ```bash ```` produz
  `<div class="chat-md-code"><pre><code class="language-bash">…</code></pre><CopyButton/></div>`,
  com o `button.link.copy` do design system copiando o texto **cru** do bloco.
- *Tabela GFM.* `remark-gfm` habilita tabela, `~~riscado~~`, checklist e autolink literal.

**Diagramas**

- Não há diagrama Mermaid nesta feature: o fluxo é linear, de um único passo de apresentação,
  e o domínio `chat` ainda não tem pasta `diagrams/` (lacuna registrada no recon §0.5). Criar a
  pasta por causa de um componente de render seria ruído. `[auto-aceito: sem diagrama porque o
  fluxo tem um passo só e a pasta de diagramas do domínio chat ainda não existe]`

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Nenhum endpoint HTTP, evento de WebSocket ou tool MCP é criado ou alterado por esta feature.
Os contratos públicos são internos ao frontend: a API do componente React e o catálogo de
classes CSS (o catálogo de classes é contrato do frontend por `shell-redesign-fdd.md` §5, que
manda **acrescentar e nunca renomear**).

**[Contrato 1] Componente `MessageMarkdown`**

- Tipo: componente React (module `frontend/src/areas/chat/MessageMarkdown.tsx`)
- Assinatura:

```tsx
/** Prefixos de URL de mídia que o dock aceita renderizar como <img>. */
export const MIDIA_PERMITIDA = ["/files/", "/mbfiles/", "/cfiles/"] as const;

export interface MessageMarkdownProps {
  /** Texto markdown do evento (`assistant_text.text` ou `tool_result.content`). */
  text: string;
  /** Variante do chip de erro de tool: fonte mono herdada, sem margens de bloco. */
  compact?: boolean;
}

export function MessageMarkdown({ text, compact }: MessageMarkdownProps): JSX.Element;
```

- Semântica:
  - `text` vazio, `undefined` coagido para `""` pelo chamador, produz um `.chat-md` vazio. O
    componente nunca lança.
  - `compact` só troca a classe do container (`chat-md compact`); o pipeline de parsing é o mesmo.
  - O componente é **puro**: mesma `text`, mesmo DOM. Não guarda estado, não faz fetch, não lê
    `localStorage`.
- Conjunto **fechado** de elementos que o componente pode produzir: `p`, `strong`, `em`, `del`,
  `code`, `pre`, `ul`, `ol`, `li`, `input[type=checkbox][disabled]` (checklist do GFM),
  `blockquote`, `h1` a `h6`, `hr`, `br`, `a`, `img`, `table`, `thead`, `tbody`, `tr`, `th`, `td`,
  mais os `div`/`button` do wrapper de bloco de código. Qualquer outra tag pedida pelo texto
  (via HTML cru) é descartada.
- Configuração do `react-markdown` (o miolo do contrato):

```tsx
<Markdown
  remarkPlugins={[remarkGfm]}
  // sem rehypePlugins: nada de rehype-raw, nada de HTML cru
  urlTransform={(url, key) => (key === "src" ? srcPermitida(url) : defaultUrlTransform(url))}
  components={{
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    ),
    img: ({ src, alt }) =>
      srcPermitida(src) ? <img className="chat-md-img" src={src} alt={alt ?? ""} loading="lazy" /> : null,
    pre: ({ node, children }) => (
      <div className="chat-md-code">
        <pre>{children}</pre>
        <CopyButton text={textoDoBloco(node)} label="Copiar" />
      </div>
    ),
  }}
>
  {text}
</Markdown>
```

  - `srcPermitida(url)`: devolve a própria URL quando ela começa por um dos `MIDIA_PERMITIDA`;
    caso contrário devolve `""` (o override de `img` então devolve `null`). Função exportada para
    o teste.
  - `textoDoBloco(node)`: lê o texto cru do nó hast (`node.children[0].children[0].value`) com
    guarda defensiva, devolvendo `""` quando a forma não bate. É o texto que o `CopyButton` copia,
    sem o `\n` final do fence.
  - `CopyButton` vem de `frontend/src/ui` (`import { CopyButton } from "../../ui"`), preservando a
    classe `button.link.copy` do design system.

**Exemplo de entrada** (o que a tool `project_get` devolve hoje, `studio/mcp/tools.py:46`):

```json
{
  "kind": "assistant_text",
  "text": "Campanha **Café da Serra** (`cafe-serra`)\n\n- produto: café em grão\n- vibe: (a encontrar na etapa 2)\n\nAbra `/files/cafe-serra/base/base_final.png` para ver a base."
}
```

**Exemplo de saída** (DOM dentro de `.chat-bubble[data-md="1"]`, resumido):

```html
<div class="chat-md">
  <p>Campanha <strong>Café da Serra</strong> (<code>cafe-serra</code>)</p>
  <ul>
    <li>produto: café em grão</li>
    <li>vibe: (a encontrar na etapa 2)</li>
  </ul>
  <p>Abra <code>/files/cafe-serra/base/base_final.png</code> para ver a base.</p>
</div>
```

**[Contrato 2] Catálogo de classes CSS acrescentadas em `chat.css`**

- Tipo: contrato DOM/CSS (`frontend/src/areas/chat/chat.css`)
- Classes **novas** (nenhuma classe existente é renomeada ou removida):

| Seletor | Papel |
| --- | --- |
| `.chat-md` | Container do markdown renderizado dentro de `.chat-bubble` ou `.chat-tool`. |
| `.chat-md.compact` | Variante do chip de erro de tool: herda fonte e cor, zera margens. |
| `.chat-md-img` | Imagem markdown aprovada pela allowlist (largura 100%, `border-radius` 8px). |
| `.chat-md-code` | Wrapper do bloco de código (posiciona o `button.link.copy` no canto). |

- Atributo **novo** no DOM existente: `data-md="1"` na `div.chat-bubble` do assistente. Serve de
  gancho estável para teste e para um futuro cenário Playwright, sem inventar classe nova.
- Regras internas do `.chat-md` (todas escopadas, nenhuma global): `p`, `ul`, `ol`, `li`, `code`,
  `pre`, `a`, `strong`, `em`, `blockquote`, `h1` a `h4`, `hr`, `table`, `th`, `td`, `img`.
- Mudança em regra existente: `white-space: pre-wrap` sai de `.chat-bubble` (`chat.css:95-103`) e
  passa a `.chat-msg.user .chat-bubble` (`chat.css:104`). O restante da regra `.chat-bubble`
  (padding, raio, tamanho, `word-break`, `max-width`) fica intacto.
- Tokens usados: só os que já existem em `frontend/src/styles/style.css` para os dois temas.
  Nenhuma cor literal (`#rrggbb`) entra em `chat.css`.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Nota |
| --- | --- | --- |
| `text` vazio, `null` ou `undefined` | Chamador coage para `""`; o componente renderiza `.chat-md` vazio | Sem `null` crash; a bolha some visualmente por não ter conteúdo |
| Markdown incompleto (`**Camp`, fence aberto) | O remark degrada para texto literal; nenhuma exceção | Requisito de convivência com `assistant_delta` (F02) |
| HTML cru no texto (`<b>`, `<script>`, `<iframe>`) | Nó `html` descartado pelo pipeline (sem `rehype-raw`); o texto adjacente sobrevive | Fecha a superfície de injeção |
| `href` com protocolo perigoso (`javascript:`, `data:`) | `defaultUrlTransform` do `react-markdown` zera o `href` | Comportamento padrão da lib, mantido de propósito |
| `src` de imagem fora da allowlist | `srcPermitida` devolve `""` e o override de `img` devolve `null` | Nada aparece, nenhuma requisição sai |
| `textoDoBloco(node)` com forma inesperada de hast | Guarda devolve `""`; o `CopyButton` copia string vazia | Nunca lança; o bloco continua visível |
| Exceção inesperada dentro do parser | Não há `ErrorBoundary` dedicado; o `ChatDock` inteiro cairia | Risco R2 da seção 10; mitigado pelo conjunto de testes e pela pureza do componente `[auto-aceito: sem ErrorBoundary novo, porque o repo não usa nenhum hoje e introduzir um padrão de tratamento de erro no núcleo do frontend seria escopo maior que a feature]` |
| `CopyButton` sem permissão de clipboard | Já tratado no design system (fallback `execCommand`, `CopyButton.tsx`) | Nada a fazer aqui |

**Estratégias de resiliência.** Não se aplicam timeouts, retries, backoff nem circuit breaker:
a feature é síncrona, local ao processo do browser e sem I/O. A única "resiliência" relevante é a
degradação para texto literal diante de markdown malformado.

**Política de fallback.** Falha de parsing não existe como estado observável no `react-markdown`
(entrada arbitrária sempre produz árvore); o fallback natural é "o texto aparece literalmente",
que é exatamente o comportamento de hoje. Ou seja, o pior caso desta feature é o estado atual.

**Invariantes**
- I1: nenhum elemento fora do conjunto fechado da seção 5 é criado a partir do texto do modelo.
- I2: nenhuma requisição de rede para host diferente do próprio Studio sai da bolha.
- I3: a bolha do usuário nunca passa pelo parser de markdown.
- I4: nenhuma classe CSS pré-existente de `chat.css` é renomeada ou removida.
- I5: o componente é puro e não guarda estado entre renders.

---

### 7. Observabilidade

O Studio é uma ferramenta local single-process sem telemetria (ADR-001); não há métrica de
runtime, log estruturado nem tracing no frontend. A observabilidade desta feature é, portanto,
**de build e de teste**, e é isso que o PR precisa evidenciar.

**Métricas**
- Delta de tamanho de `studio/web/dist/` (bytes brutos e gz do chunk principal) medido antes e
  depois de `make frontend-build`, colado no corpo do PR. Referência de plano: ~40 KB gz.
- Contagem de testes Vitest do arquivo novo (alvo: 9 casos, seção 9).

**Logs**
- Nenhum `console.log`/`console.warn` novo. O lint do repo (`npm run lint`) é a guarda.

**Tracing**
- Não se aplica.

**Dashboards e alertas**
- Não se aplica. As guardas automáticas que fazem o papel de alerta são: o job `frontend` do CI
  (typecheck, lint, vitest e o rebuild que reprova se o `dist/` commitado divergir, `CLAUDE.md`
  seção Wave 10 item 2) e `tests/test_adr010_fronteira_nucleo.py` (titularidade de núcleo).
- Gancho manual de inspeção: o atributo `data-md="1"` na bolha do assistente permite conferir no
  DevTools, ou num futuro cenário Playwright, quais bolhas passaram pelo parser.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `react-markdown` | `10.1.0` (pinada, sem `^`) | Dependência de runtime nova. A linha 10.x é a que declara peer `react: >=18`, compatível com o React 19.2 do repo. Em v9 a lib passou a **ignorar HTML cru por padrão** e trocou `transformImageUri`/`transformLinkUri` por `urlTransform`: a API usada aqui é a da 10.x. |
| `remark-gfm` | `4.0.1` (pinada, sem `^`) | Tabela, `~~riscado~~`, checklist e autolink literal. A 4.x é a linha compatível com o remark do `react-markdown` 10.x. |
| React | 19.2 (já no repo) | `frontend/package.json:20-21`. |
| TypeScript | 5.7 estrito (já no repo) | As duas libs trazem tipos próprios; nenhum `@types/*` extra é preciso. |
| Vitest + jsdom | 3.x / 25.x (já no repo) | `frontend/vite.config.ts` com `environment: "jsdom"`, `setupFiles: ["./src/setupTests.ts"]`. |
| `frontend/src/ui` (`CopyButton`) | interno | Reuso do design system (Wave 10 · E2), sem segunda cópia. |

`[auto-aceito: versões pinadas exatas em vez do "^" usado no resto do package.json, porque o card
manda "versões pinadas"; a implementação fixa a versão exata que o npm resolver e a registra no PR
junto do delta de bundle]`

**Garantias de compatibilidade**
- **Aditiva no DOM.** Nenhuma classe existente de `chat.css` muda de nome ou desaparece; só entram
  classes novas com prefixo `.chat-md*` e o atributo `data-md`. Contrato de classes preservado
  (`shell-redesign-fdd.md` §5).
- **Contrato de API intocado.** Nenhuma rota, nenhum modelo Pydantic, nenhum evento de WS e
  nenhuma tool mudam. Logo `frontend/src/api/schema.ts` **não** é regenerado e a guarda de drift
  do CI segue verde sem ação.
- **Protocolo do chat intocado.** `frontend/src/areas/chat/types.ts` fica como está: o
  `assistant_text` já tem `text?: string`.
- **Convivência com F02 (chat-feedback).** Se o card #86 introduzir `assistant_delta`, o
  componente já tolera marcação parcial (fluxo alternativo da seção 4 e teste 8 da seção 9).
  A região de `ChatDock.tsx` tocada aqui (o `switch` do `Message`, `:280-309`) é distinta das
  regiões que F02 toca (composer e status, `:240-266`), como prevê a wave em "Conflitos de
  arquivo previstos".
- **Convivência com F11 (base-upscale-chat).** F11 mexe no `MediaCard` (`ChatDock.tsx:311+`), que
  esta feature não toca.
- **Rollback.** Reverter é remover as duas chamadas do componente, o arquivo novo, as regras
  `.chat-md*` e as duas deps, e rodar `make frontend-build`. Nenhum dado em disco muda, nenhuma
  migração existe.

---

### 9. Critérios de aceite técnicos

Testes Vitest em `frontend/src/areas/chat/MessageMarkdown.test.tsx` (os seis primeiros são os
exigidos pelo card #85):

1. **Negrito.** `**Campanha X**` renderiza um elemento `strong` com texto `Campanha X`, e o
   `textContent` do container não contém `*`.
2. **Lista.** `- a\n- b` renderiza um `ul` com exatamente dois `li` (`a` e `b`).
3. **HTML cru escapado.** O texto `<b>oi</b> <script>window.x=1</script>` não produz elemento
   `b` nem `script` (`container.querySelector("b")` e `("script")` são `null`), e `window.x`
   continua `undefined`.
4. **Link externo.** `[site](https://exemplo.com)` produz `a[href="https://exemplo.com"]` com
   `target="_blank"` e `rel="noopener noreferrer"`.
5. **Imagem externa não renderiza.** `![x](https://exemplo.com/a.png)` não produz nenhum `img`;
   o caso irmão `![base](/files/p1/base/x.png)` produz um `img` com esse `src`. Cobre também
   `/mbfiles/` e `/cfiles/`.
6. **Texto do usuário não passa pelo parser.** Renderizando o `ChatDock` (ou o `Message`) com um
   evento `kind: "user"` e texto `**a**`, o DOM não tem `strong` e o `textContent` contém `**a**`.
7. **Bloco de código.** Uma cerca com linguagem produz `pre > code.language-bash` dentro de
   `.chat-md-code` e um `button.link.copy` ao lado; clicar copia o texto cru do bloco.
8. **Markdown incompleto tolerado.** `**Camp` renderiza sem lançar e o `textContent` contém
   `**Camp`.
9. **Escopo de aplicação.** Um `tool_result` com `is_error: true` e conteúdo `**falhou**` renderiza
   `strong` dentro do chip `.chat-tool[data-err="1"]`; um `tool_result` de sucesso continua não
   renderizando nada.

Critérios de processo e de núcleo:

10. `make frontend-verify` passa (typecheck estrito, ESLint e a suíte Vitest inteira, incluindo os
    testes pré-existentes `useChatSocket.test.ts` e os das telas em `studio/etapas/*/ui/`).
11. `make frontend-build` roda e `studio/web/dist/` é commitado no mesmo PR (o job `frontend` do CI
    reprova drift de bundle).
12. `make verify` (ruff + pytest) segue verde, com a branch declarada em `TITULARES_DO_NUCLEO`
    (`tests/test_adr010_fronteira_nucleo.py`) com os prefixos `frontend/` e `studio/web/`.
13. `frontend/src/api/schema.ts` **não** muda (evidência: `git diff --name-only` sem esse arquivo),
    confirmando que nenhuma rota nem modelo foi tocado.
14. O corpo do PR registra o delta de bundle (bruto e gz) e as versões exatas das duas deps novas.
15. Nenhuma classe pré-existente de `chat.css` é renomeada ou removida (evidência: o diff do CSS só
    acrescenta blocos e move `white-space` de um seletor para outro mais específico).

Critérios `[cross-feature]`:

16. `[cross-feature]` **F02 chat-feedback (card #86).** No estado integrado, se F02 emitir
    `assistant_delta`, cada quadro parcial passado a `MessageMarkdown` renderiza sem exceção e sem
    desmontar o dock; a marcação incompleta aparece literal até fechar. Evidência: teste 8 desta
    feature mais uma verificação manual no estado integrado da W5.
17. `[cross-feature]` **F02 chat-feedback, mesmo arquivo.** O rebase de F02 sobre F01 (ordem de
    integração da wave: F04, F05, F01, F03, F02) preserva as duas chamadas de `MessageMarkdown` no
    `switch` do `Message`. Evidência: `grep MessageMarkdown frontend/src/areas/chat/ChatDock.tsx`
    devolve duas ocorrências depois do merge de F02.
18. `[cross-feature]` **F11 base-upscale-chat (card #94).** As mensagens de texto que acompanham as
    imagens do `base_review` chegam formatadas, e o `MediaCard` continua sendo o único responsável
    por renderizar mídia (imagem markdown externa segue bloqueada). Evidência: inspeção no estado
    integrado da sub-wave 2.

---

### 10. Riscos e mitigação

#### R1. Superfície de injeção via texto do modelo

- **Probabilidade:** baixa
- **Impacto:** alto se materializado. O texto vem do CLI `claude` e de tools do MCP, mas parte do
  conteúdo é eco de dados do usuário (nome de campanha, nome de arquivo, saída de erro). Renderizar
  HTML cru abriria XSS dentro de uma página que fala com a API local sem autenticação (ADR-001).
- **Mitigação:**
  - Não instalar nem importar `rehype-raw`; nenhum `rehypePlugins`.
  - Nunca usar `dangerouslySetInnerHTML` no componente.
  - Manter o `defaultUrlTransform` do `react-markdown` para `href` (bloqueia `javascript:`).
  - Allowlist estrita de `src` de imagem nos três mounts estáticos do Studio.
  - Teste 3 da seção 9 como guarda de regressão permanente.
- **Plano de contingência:** se algum caso escapar, o remédio imediato é reverter as duas chamadas
  de `MessageMarkdown` em `ChatDock.tsx` (volta ao texto puro) e rebuildar o dist.

#### R2. Exceção no parser derruba o dock inteiro

- **Probabilidade:** baixa
- **Impacto:** médio. Sem `ErrorBoundary`, uma exceção durante o render do markdown propagaria e
  desmontaria a árvore do `ChatDock` (o dock é montado sempre no `Shell`).
- **Mitigação:**
  - Componente puro, sem estado nem I/O, com as duas funções auxiliares (`srcPermitida`,
    `textoDoBloco`) escritas defensivamente e testadas.
  - Teste 8 cobre marcação incompleta, que é o cenário realista de entrada malformada.
  - `text` sempre coagido para string no chamador.
- **Plano de contingência:** se aparecer uma classe de entrada que quebre, envolver o `Markdown`
  num `ErrorBoundary` local que degrada para `<span>{text}</span>`; fica registrado como opção,
  não implementado agora.

#### R3. Crescimento do bundle sempre carregado

- **Probabilidade:** alta (é certeza de que cresce; o risco é o tamanho surpreender)
- **Impacto:** baixo. O dock é importado estaticamente pelo `Shell`, então as ~40 KB gz caem no
  chunk principal. Como o bundle é servido de `localhost` pelo mesmo processo, o efeito percebido
  é próximo de zero; o custo real é o `studio/web/dist/` versionado ficar maior em cada commit.
- **Mitigação:**
  - Medir e registrar o delta no PR (critério 14).
  - Não instalar realce de sintaxe, que é o item que de fato pesa.
  - `[auto-aceito: import estático em vez de React.lazy, porque a app roda em loopback, o dock é
    sempre montado e um chunk assíncrono só adicionaria um estado de carregamento sem ganho real]`
- **Plano de contingência:** se o delta medido passar de ~60 KB gz, trocar por `React.lazy` +
  `Suspense` só no `MessageMarkdown` e registrar a mudança no PR.

#### R4. Conflito de rebase em `ChatDock.tsx` e no bundle

- **Probabilidade:** média
- **Impacto:** baixo. A wave prevê F01, F02, F03, F08, F09, F10 e F11 tocando o mesmo arquivo.
- **Mitigação:**
  - Manter o diff mínimo e confinado ao `switch` do `Message` (`:280-309`), sem reformatar nada em
    volta.
  - Nunca resolver conflito em `studio/web/dist/` nem em `schema.ts` à mão: regenerar
    (recon §7, wave §Conflitos).
  - F01 entra cedo na ordem de integração (terceira, depois de F04 e F05), o que joga o custo do
    rebase para as frentes seguintes, que já esperam por ele.
- **Plano de contingência:** rebase com `git-rebase` e novo `make frontend-build` antes de repetir
  a validação.

#### R5. Regressão visual silenciosa na bolha

- **Probabilidade:** média
- **Impacto:** baixo. Tirar o `white-space: pre-wrap` da regra genérica pode alterar o
  espaçamento de mensagens que hoje dependem de quebras de linha cruas.
- **Mitigação:**
  - Reaplicar `pre-wrap` explicitamente na bolha do usuário, que é o único caso que continua sendo
    texto puro.
  - Dar ao `.chat-md p` margem vertical equivalente ao espaçamento de hoje.
  - Conferir os dois temas manualmente (claro e escuro) antes do PR; o CSS só usa tokens, então
    não há cor literal para divergir.
  - O baseline de `textContent` de QA (`docs/qa/reports/2026-09-03-react-e0-v2/textcontent/`) é
    anterior ao chat e não contém texto do dock (verificado), então esta mudança não pode sujá-lo.
- **Plano de contingência:** reverter só o bloco de CSS, mantendo o componente.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Titularidade de núcleo e ambiente da worktree | - | `tests/test_adr010_fronteira_nucleo.py` (entrada no topo de `TITULARES_DO_NUCLEO`), `.env.local` com `skip-worktree` | 12 |
| 2 | Dependências pinadas e `npm ci` | 1 | `frontend/package.json`, `frontend/package-lock.json` | 14 |
| 3 | Componente `MessageMarkdown` (parser, `urlTransform`, overrides de `a`/`img`/`pre`) | 2 | `frontend/src/areas/chat/MessageMarkdown.tsx` | 1, 2, 3, 4, 5, 7, 8 |
| 4 | Ligação no dock (`assistant_text` e `tool_result` de erro) | 3 | `frontend/src/areas/chat/ChatDock.tsx` (`:288-293` e `:297`) | 6, 9 |
| 5 | Estilos de markdown nos dois temas | 4 | `frontend/src/areas/chat/chat.css` (`.chat-md*`, `pre-wrap` para `.chat-msg.user .chat-bubble`) | 15 |
| 6 | Testes Vitest | 3, 4 | `frontend/src/areas/chat/MessageMarkdown.test.tsx` | 1 a 9 |
| 7 | Verificação e bundle | 5, 6 | `make frontend-verify`, `make frontend-build`, commit de `studio/web/dist/`, `make verify` | 10, 11, 12, 13 |
| 8 | PR pelo gate `ft-pr` com delta de bundle e versões | 7 | corpo do PR (`.agents/gates/ft-pr.md`) | 14 |

**Arquivos previstos (detalhe)**

| Arquivo | Ação |
| --- | --- |
| `frontend/src/areas/chat/MessageMarkdown.tsx` | novo |
| `frontend/src/areas/chat/MessageMarkdown.test.tsx` | novo |
| `frontend/src/areas/chat/ChatDock.tsx` | editado (2 pontos do `switch` do `Message`) |
| `frontend/src/areas/chat/chat.css` | editado (classes novas + `pre-wrap` movido) |
| `frontend/package.json` | editado (2 deps pinadas) |
| `frontend/package-lock.json` | editado (regenerado pelo npm) |
| `studio/web/dist/**` | regenerado por `make frontend-build` |
| `tests/test_adr010_fronteira_nucleo.py` | editado (titularidade) |

Contratos (seção 5): 2
Fluxos principais (seção 4): 1
Arquivos previstos: 8

**Decisão direta × SDD:** 2 contratos (≤3) **e** 1 fluxo **e** 8 arquivos (≤8) → **implementação
direta**, sem pipeline SDD/Compozy.

**Núcleo a declarar em `TITULARES_DO_NUCLEO`:** prefixos `frontend/` e `studio/web/`, na entrada
da branch `feature/adh-os-20260906-03-chat-markdown`, com o motivo apontando o card #85 e a
ADR-031 (dependência nova de frontend em `package.json`, que é núcleo) mais ADR-032. **Não** são
declarados `studio/app.py`, `studio/steps.py`, `studio/config.py`, `studio/higgsfield.py` nem
`studio/etapas/__init__.py`: esta frente não os toca.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas (modo batch)**

| # | Decisão | Fonte / razão |
| --- | --- | --- |
| A1 | `react-markdown` 10.x + `remark-gfm` 4.x, **versões pinadas exatas** (sem `^`), contrariando o `^` usado no resto do `package.json`. | O card #85 manda "versões pinadas"; a linha 10.x é a que casa com React 19 e com a API `urlTransform`. A versão exata resolvida pelo npm entra no PR. |
| A2 | HTML cru é **descartado** pelo pipeline, não escapado e exibido. | Comportamento padrão do `react-markdown` desde a v9 sem `rehype-raw`. É a opção mais conservadora e a que o card pede ("sem HTML cru, não usar rehype-raw"). O critério 3 afirma "nenhum elemento criado", que é o que de fato garante segurança. |
| A3 | Imagem fora da allowlist renderiza **nada** (nem o texto alternativo). | Leitura literal do card ("externas não renderizam"). Alternativa descartada: mostrar o `alt` como texto, que exigiria decidir um estilo de placeholder sem fonte. |
| A4 | **Todos** os links abrem em nova aba, inclusive relativos. | O card diz "links em nova aba com rel=noopener" sem distinguir. Reforço: o dock é um painel fixo do shell; navegar a própria aba mataria a conversa em andamento. |
| A5 | Bloco de código implementado pelo override de `pre` (lendo o texto cru do nó hast), não pelo override de `code`. | Na v9+ o `react-markdown` removeu a prop `inline` de `code`; distinguir inline de bloco pelo `pre` é o caminho estável. |
| A6 | Sem realce de sintaxe por linguagem. | Não está no card; custo de bundle desproporcional para uma ferramenta local. Fidelidade ao escopo (ADR-004: o que não foi pedido não entra). |
| A7 | Import estático do componente, sem `React.lazy`. | App em loopback, dock sempre montado; um chunk assíncrono só somaria estado de carregamento. Gatilho de revisão registrado em R3 (delta > ~60 KB gz). |
| A8 | Sem `ErrorBoundary` novo. | O repositório não usa nenhum hoje; introduzir o padrão no núcleo do frontend seria escopo maior que a feature. Contingência registrada em R2. |
| A9 | Sem diagrama Mermaid. | Fluxo de um passo só; o domínio `chat` ainda não tem pasta `diagrams/` (recon §0.5). |
| A10 | `white-space: pre-wrap` movido de `.chat-bubble` para `.chat-msg.user .chat-bubble` em vez de removido. | O card manda tirar da bolha do assistente; o usuário continua sendo texto puro e precisa da propriedade. Não é renomeação de classe, então o contrato do catálogo de classes é preservado. |
| A11 | Atributo novo `data-md="1"` na bolha do assistente. | Gancho de inspeção e de teste estável sem inventar classe; aditivo, alinhado com "acrescentar e nunca renomear" (`shell-redesign-fdd.md` §5). |
| A12 | Markdown aplicado também no `tool_result` de erro (variante `compact`), e **não** no `notify`, no `chat-tool` de sucesso nem nos cartões `ask`/`show`. | Recorte exato do card ("aplicar só em assistant_text e nos tool_result de erro"). |
| A13 | `docs/domains/chat/hld.md` **não** é editado por esta frente; o componente fica apenas listado aqui. | Instrução do brief da W3 e do recon §0.6: a atualização de HLD é da W5 via `dd-parallel-doc-sync`. |
| A14 | Sem cenário Playwright novo em `scripts/qa/cenarios/`. | Não existe `chat.py` (recon §0.5) e a regra da wave é não editar cenários existentes; criar a suíte de QA do chat é trabalho próprio, fora deste card. |

**Pendências para o gate em lote**

| # | Pendência | Por que não foi auto-aceita |
| --- | --- | --- |
| P1 | Aceitar ~40 KB gz a mais no chunk **sempre carregado** de `studio/web/dist/`, que é versionado em git e cresce a cada commit de bundle. | É um custo permanente no repositório, não só na experiência do usuário. O card e o plano (`plano-chat-orquestrador.md:331`) preveem o número, e o dono aprovou a wave em lote, mas o trade-off "bundle versionado maior" merece registro explícito para a retro. Gatilho objetivo já definido em R3: acima de ~60 KB gz medidos, trocar por `React.lazy` antes de abrir o PR. |
| P2 | Nenhuma outra. Não há divergência com contrato publicado (`frontend/src/api/schema.ts` não muda), não há merge, não há remoção destrutiva e não há "porquê" de negócio sem fonte. | Registro de auditoria. |
