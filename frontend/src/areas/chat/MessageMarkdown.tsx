// Markdown na bolha do assistente (Wave 11 · F01, card #85) — `[extensão]` do chat (ADR-036).
//
// As tools do MCP devolvem markdown por construção (`studio/mcp/tools.py`) e o agente escreve
// markdown porque é o formato natural do CLI `claude`. Até aqui o dock renderizava esse texto cru,
// então asterisco, crase e hífen de lista apareciam literais na tela.
//
// A superfície de injeção é fechada POR CONSTRUÇÃO, não por sanitização: sem `rehypePlugins` e sem
// `rehype-raw`, a lib ESCAPA o HTML cru e o exibe como texto literal em vez de convertê-lo em
// elemento — um `<script>` vindo do modelo aparece escrito na bolha e não vira nó `script`.
// Nunca usar `dangerouslySetInnerHTML` aqui.
//
// Ver `docs/domains/chat/features/chat-markdown-fdd.md` (seções 5 e 6).
import Markdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { CopyButton } from "../../ui";

/**
 * Prefixos de URL de mídia que o dock aceita renderizar como `<img>`.
 *
 * São os três mounts estáticos do próprio Studio (`studio/app.py`): tudo o que não começa por um
 * deles é externo e não renderiza, para que nenhuma requisição saia do loopback (ADR-001).
 */
export const MIDIA_PERMITIDA = ["/files/", "/mbfiles/", "/cfiles/"] as const;

/** A própria URL quando ela é de um mount do Studio; `""` (falsy) em qualquer outro caso. */
export function srcPermitida(url: unknown): string {
  const u = typeof url === "string" ? url : "";
  return MIDIA_PERMITIDA.some((prefixo) => u.startsWith(prefixo)) ? u : "";
}

/**
 * `urlTransform` do pipeline: allowlist estrita para `src`, `defaultUrlTransform` para o resto.
 *
 * O padrão da lib já zera `href` com protocolo perigoso (`javascript:`, `data:`); mantê-lo é
 * de propósito.
 */
export function transformarUrl(url: string, key: string): string {
  return key === "src" ? srcPermitida(url) : defaultUrlTransform(url);
}

/**
 * Texto cru de um bloco de código a partir do nó hast do `<pre>` (`pre > code > text`).
 *
 * Defensiva de ponta a ponta: qualquer forma inesperada devolve `""` em vez de lançar — uma
 * exceção aqui derrubaria o dock inteiro, que não tem ErrorBoundary (risco R2 do FDD).
 */
export function textoDoBloco(node: unknown): string {
  const filhos = (n: unknown): unknown[] => {
    const c = (n as { children?: unknown } | undefined)?.children;
    return Array.isArray(c) ? c : [];
  };
  const valor = (filhos(filhos(node)[0])[0] as { value?: unknown } | undefined)?.value;
  return typeof valor === "string" ? valor.replace(/\n$/, "") : "";
}

/**
 * Conjunto FECHADO de overrides. Todo o resto (`p`, `ul`, `li`, `strong`, `code`, `table`…) usa o
 * mapeamento padrão do react-markdown.
 */
const COMPONENTES: Components = {
  // O dock é um painel fixo do shell: navegar a própria aba mataria a conversa em andamento.
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  // Imagem fora da allowlist não vira elemento algum (nem o `alt` como texto).
  img: ({ src, alt }) => {
    const url = srcPermitida(src);
    return url ? <img className="chat-md-img" src={url} alt={alt ?? ""} loading="lazy" /> : null;
  },
  // O override é de `pre` e não de `code` porque a v9+ removeu a prop `inline` de `code`: o `pre` é
  // o jeito estável de distinguir bloco de inline.
  pre: ({ node, children }) => (
    <div className="chat-md-code">
      <pre>{children}</pre>
      <CopyButton text={textoDoBloco(node)} label="Copiar" />
    </div>
  ),
};

export interface MessageMarkdownProps {
  /** Texto markdown do evento (`assistant_text.text` ou `tool_result.content`). */
  text: string;
  /** Variante do chip de erro de tool: fonte mono herdada, sem margens de bloco. */
  compact?: boolean;
}

/**
 * Renderiza o texto do assistente como markdown. Componente PURO: mesma `text`, mesmo DOM — sem
 * estado, sem fetch, sem `localStorage`.
 */
export function MessageMarkdown({ text, compact }: MessageMarkdownProps) {
  return (
    <div className={compact ? "chat-md compact" : "chat-md"}>
      <Markdown remarkPlugins={[remarkGfm]} urlTransform={transformarUrl} components={COMPONENTES}>
        {text}
      </Markdown>
    </div>
  );
}
