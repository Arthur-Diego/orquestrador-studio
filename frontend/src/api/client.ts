/**
 * Client tipado: `api()` (http.ts) + os caminhos do contrato publicado (schema.ts).
 *
 * O que o tipo garante aqui é o que o `/openapi.json` do FastAPI de fato descreve:
 *
 * - **a rota existe** — `"/api/projects/{pid}/guide"` compila, `"/api/project/{pid}/guide"` não;
 * - **os parâmetros de rota estão todos preenchidos** — o template `{pid}` obriga a chave `pid`,
 *   e o valor sai sempre por `encodeURIComponent` (hoje isso é responsabilidade de cada chamador
 *   no vanilla, repetida ~200 vezes);
 * - **o corpo JSON bate com o modelo Pydantic** — `NewProject`, `ProjectPatch`, `SelectReq`… todos
 *   vêm de `components["schemas"]`;
 * - **os parâmetros de query existem e têm o tipo certo**.
 *
 * O que ele NÃO garante é a RESPOSTA, porque o backend não declara `response_model` em rota
 * nenhuma (ver a nota longa em `types.ts`). `request()` devolve `unknown`, e quem quiser declarar
 * o que espera envolve a chamada com `resposta<T>()` — uma asserção explícita e greppável. As
 * asserções do núcleo estão todas concentradas em `queries.ts`.
 */
import { api } from "./http";
import type { paths } from "./schema";

/** Toda rota publicada em `/openapi.json` — 201 delas. */
export type Rota = keyof paths;

export type Metodo = "get" | "put" | "post" | "delete" | "patch";

/**
 * As rotas que expõem o método `M`.
 *
 * O `openapi-typescript` escreve os métodos ausentes como `put?: never`, então ler
 * `paths[P][M]` devolve `undefined` quando o método não existe e o objeto da operação quando
 * existe — é esse o teste abaixo.
 */
export type RotasCom<M extends Metodo> = {
  [P in Rota]: undefined extends paths[P][M] ? never : P;
}[Rota];

type Operacao<P extends Rota, M extends Metodo> = paths[P][M];

/** Nomes dos parâmetros de rota de um template: `"/api/projects/{pid}/guide/{step}"` → `"pid" | "step"`. */
export type ParamsDaRota<S extends string> = S extends `${string}{${infer Nome}}${infer Resto}`
  ? Nome | ParamsDaRota<Resto>
  : never;

type ParamsDeQuery<P extends Rota, M extends Metodo> = Operacao<P, M> extends {
  parameters: { query?: infer Q };
}
  ? Q
  : never;

type CorpoJson<P extends Rota, M extends Metodo> = Operacao<P, M> extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;

type ValorDeParam = string | number;

/** `params` só é exigido — e só é aceito — quando o template tem `{placeholders}`. */
type ChaveParams<P extends Rota> = [ParamsDaRota<P>] extends [never]
  ? { params?: never }
  : { params: Record<ParamsDaRota<P>, ValorDeParam> };

type ChaveQuery<P extends Rota, M extends Metodo> = [ParamsDeQuery<P, M>] extends [never]
  ? { query?: never }
  : { query?: ParamsDeQuery<P, M> };

type ChaveCorpo<P extends Rota, M extends Metodo> = [CorpoJson<P, M>] extends [never]
  ? { body?: never }
  : { body: CorpoJson<P, M> };

export type Opcoes<P extends Rota, M extends Metodo> = ChaveParams<P> &
  ChaveQuery<P, M> &
  ChaveCorpo<P, M> & {
    /** Repassado a `fetch` DEPOIS do `Content-Type` — ver a nota de ordem em `http.ts`. */
    init?: RequestInit;
  };

function preencher(template: string, params?: Partial<Record<string, ValorDeParam>>): string {
  return template.replace(/\{([^}]+)\}/g, (_todo, nome: string) => {
    const v = params?.[nome];
    if (v === undefined || v === null) throw new Error(`rota(): parâmetro ausente em ${template}: ${nome}`);
    return encodeURIComponent(String(v));
  });
}

/** `params` de `rota()`: exigido só quando o template tem `{placeholders}`, e só com as chaves dele. */
type ArgsRota<P extends Rota> = [ParamsDaRota<P>] extends [never]
  ? []
  : [params: Record<ParamsDaRota<P>, ValorDeParam>];

/**
 * Preenche os `{placeholders}` de um template com `encodeURIComponent`, igual ao vanilla
 * (`api(\`/api/projects/${encodeURIComponent(pid)}/guide\`)`) — só que o template vem do contrato e
 * as chaves de `params` são conferidas pelo compilador.
 *
 * Exportada porque as telas também precisam montar URL para coisas que não passam por `request()`
 * — o `apiUpload()` multipart, por exemplo, ou o `<img src>` de um artefato.
 */
export function rota<P extends Rota>(template: P, ...args: ArgsRota<P>): string {
  return preencher(template, args[0] as Partial<Record<string, ValorDeParam>> | undefined);
}

/**
 * Serializa a query string.
 *
 * `undefined` e `null` são omitidos; booleanos viram `1`/`0`, que é a convenção do vanilla
 * (`/api/creditos/balance${refresh ? "?refresh=1" : ""}`, `ui.js:252`) e o que o FastAPI já
 * interpreta. Para omitir um parâmetro, não passe a chave — `false` vira `0` e VAI.
 */
function queryString(query: unknown): string {
  if (!query || typeof query !== "object") return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(query as Record<string, unknown>)) {
    if (v === undefined || v === null) continue;
    sp.append(k, typeof v === "boolean" ? (v ? "1" : "0") : String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/**
 * `opcoes` é obrigatório quando a rota tem `{placeholders}` ou exige corpo JSON, e opcional quando
 * não tem nem uma coisa nem outra. Sem isto, `apiGet("/api/projects/{pid}/guide")` — sem o `pid` —
 * compilaria: um parâmetro opcional pode ser omitido inteiro, e os campos obrigatórios de dentro
 * dele nunca chegam a ser cobrados.
 */
type PrecisaOpcoes<P extends Rota, M extends Metodo> = [ParamsDaRota<P>] extends [never]
  ? [CorpoJson<P, M>] extends [never]
    ? false
    : true
  : true;

type ArgsOpcoes<P extends Rota, M extends Metodo> = PrecisaOpcoes<P, M> extends true
  ? [opcoes: Opcoes<P, M>]
  : [opcoes?: Opcoes<P, M>];

/**
 * Uma requisição ao contrato publicado. Toda chamada tipada do frontend passa por aqui.
 *
 * Devolve `Promise<unknown>`, e isso é honestidade, não preguiça: o backend não declara
 * `response_model` em rota nenhuma, então o contrato publicado não diz nada sobre o corpo da
 * resposta. Para declarar o que se espera, envolva com `resposta<T>()` — que é uma **asserção**
 * explícita, greppável, e cujo lugar certo é `queries.ts`.
 *
 * (O tipo da resposta não é um parâmetro genérico desta função de propósito: o TypeScript não faz
 * inferência parcial de argumentos de tipo, então passar `<Step[]>` explicitamente desligaria a
 * inferência do template da rota e todos os parâmetros de rota do app virariam obrigatórios de uma
 * vez. `resposta<T>()` separado mantém as duas coisas funcionando.)
 */
export function request<M extends Metodo, P extends RotasCom<M>>(
  metodo: M,
  template: P,
  ...resto: ArgsOpcoes<P, M>
): Promise<unknown> {
  const o = (resto[0] ?? {}) as {
    params?: Record<string, ValorDeParam>;
    query?: unknown;
    body?: unknown;
    init?: RequestInit;
  };
  const url = preencher(template, o.params) + queryString(o.query);
  const init: RequestInit = { ...o.init };
  // GET não leva `method` no vanilla (`api(path)` sem opts) — mandar `method: "GET"` explícito é
  // equivalente para o `fetch`, mas o default sem a chave é o que o `app.js` faz hoje.
  if (metodo !== "get") init.method = metodo.toUpperCase();
  if (o.body !== undefined) init.body = JSON.stringify(o.body);
  return api(url, init);
}

/**
 * Asserção do tipo da resposta: `resposta<Step[]>(apiGet("/api/steps"))`.
 *
 * Não valida nada em runtime — declara o que o chamador espera e assume a responsabilidade. Existe
 * para que toda asserção de resposta do frontend seja uma ocorrência desta função, fácil de
 * auditar e de remover em bloco no dia em que o backend declarar `response_model`.
 */
export function resposta<T>(p: Promise<unknown>): Promise<T> {
  return p as Promise<T>;
}

/** Atalhos por método. Mesma semântica de `request`. */
export const apiGet = <P extends RotasCom<"get">>(template: P, ...resto: ArgsOpcoes<P, "get">) =>
  request("get", template, ...resto);

export const apiPost = <P extends RotasCom<"post">>(template: P, ...resto: ArgsOpcoes<P, "post">) =>
  request("post", template, ...resto);

export const apiPatch = <P extends RotasCom<"patch">>(template: P, ...resto: ArgsOpcoes<P, "patch">) =>
  request("patch", template, ...resto);

export const apiPut = <P extends RotasCom<"put">>(template: P, ...resto: ArgsOpcoes<P, "put">) =>
  request("put", template, ...resto);

export const apiDelete = <P extends RotasCom<"delete">>(template: P, ...resto: ArgsOpcoes<P, "delete">) =>
  request("delete", template, ...resto);
