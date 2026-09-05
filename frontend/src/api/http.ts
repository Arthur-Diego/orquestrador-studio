/**
 * Camada HTTP do frontend — equivalente EXATO do helper `api()` de `studio/web/app.js:17-21`.
 *
 * Wave 10 · E1 (card [REACT-02], ADR-031). Esta é uma migração de tecnologia, não de
 * comportamento: tudo aqui existe para reproduzir o vanilla byte a byte, inclusive o que parece
 * errado. Duas coisas em particular NÃO são bugs a consertar:
 *
 * 1. **`Content-Type: application/json` vai em TODA requisição, inclusive em GET.** GET não tem
 *    corpo, então o cabeçalho é semanticamente inútil — e mesmo assim o vanilla o manda desde
 *    sempre. Tirá-lo é mudar o que trafega na rede; a auditoria de contrato (`make qa-api`) e
 *    qualquer proxy/middleware que olhe cabeçalho veriam requisições diferentes.
 * 2. **O `...opts` vem DEPOIS do `headers`.** Quem passar `headers` em `opts` SUBSTITUI o objeto
 *    inteiro e perde o `Content-Type` — não há merge. Hoje nenhum chamador faz isso (verificado em
 *    `studio/etapas/<id>/view.js` e `studio/web/*.js`: a única outra ocorrência de `headers` é o
 *    `fetch` próprio de `edit/view.js:147`, que não passa por aqui), mas a ordem é contrato.
 *
 * O mapeamento de erro é o outro invariante: `!r.ok` → `Error` cuja `message` é
 * `body.detail || r.statusText`. As telas jogam essa string direto no toast
 * (`ctx.api(...).catch(e => toast(e.message))`), então o texto é visível ao usuário e a ADR-004
 * o congela. Observe o `||` (não `??`): `detail: ""` cai para o `statusText`.
 */

/**
 * O que `api()` e `apiUpload()` lançam quando a resposta não é `ok`.
 *
 * É um `Error` COMUM com dois campos anexados — de propósito, e não uma subclasse. Uma subclasse
 * mudaria `err.name` de `"Error"` para `"ApiError"`, e `err.name` é observável por qualquer
 * `catch` que já exista ou venha a existir. `status` e `body` são adição pura: o vanilla os
 * descartava, e ter o código HTTP à mão evita que a próxima frente reabra a resposta para
 * distinguir 409 (gate de login do Higgsfield) de 404.
 */
export interface ApiError extends Error {
  /** Código HTTP da resposta que falhou. */
  status: number;
  /** Corpo já desserializado (ou `{}` quando não era JSON). O `detail` do FastAPI mora aqui. */
  body: unknown;
}

/** Estreita um `unknown` de `catch` para `ApiError`. */
export function isApiError(e: unknown): e is ApiError {
  return e instanceof Error && typeof (e as Partial<ApiError>).status === "number";
}

/** Corpo de erro do FastAPI. `detail` é `string` na app inteira, menos no 422, que manda lista. */
type CorpoDeErro = { detail?: unknown } | null | undefined;

async function erroDaResposta(r: Response): Promise<ApiError> {
  const body: unknown = await r.json().catch(() => ({}));
  const detail = (body as CorpoDeErro)?.detail;
  // O `as string` reproduz a coerção do vanilla: `new Error(x)` faz ToString em `x`. Num 422 o
  // `detail` é uma lista de objetos e a mensagem sai como o JS a produz hoje — igual, não melhor.
  //
  // Divergência deliberada e única: o vanilla faz `(await r.json().catch(() => ({}))).detail`, que
  // estoura `TypeError` se o corpo do erro for o literal `null`. O `?.` acima devolve
  // `Error(statusText)` nesse caso. Este backend nunca responde `null` num erro (o FastAPI sempre
  // manda `{"detail": ...}`), então a diferença não é alcançável a partir do app — mas trocar um
  // crash por uma mensagem útil num caminho inalcançável é o único ponto em que não copiei o
  // vanilla ao pé da letra.
  const err = new Error((detail || r.statusText) as string) as ApiError;
  err.status = r.status;
  err.body = body;
  return err;
}

/**
 * `fetch` + JSON, igual ao `api()` do `app.js`. Devolve o corpo desserializado.
 *
 * Sem tipo de resposta porque o backend não declara `response_model` em rota nenhuma: o
 * `/openapi.json` traz `"schema": {}` em todos os 200, e o `schema.ts` gerado reflete isso como
 * `unknown` (ver `types.ts`). Use os wrappers tipados de `client.ts` em vez de chamar isto direto.
 */
export async function api(path: string, opts: RequestInit = {}): Promise<unknown> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw await erroDaResposta(r);
  return r.json();
}

/** Campos extras de um upload multipart. `undefined`/`null` são omitidos, como no vanilla. */
export type CamposExtras = Record<string, string | number | boolean | Blob | null | undefined>;

/**
 * POST multipart — equivalente exato de `Studio.ui.upload()` (`studio/web/ui.js:126-134`).
 *
 * **Por que mora aqui e não na biblioteca de UI da E2:** `upload` não toca DOM. O que ele faz é
 * montar um `FormData`, mandar um POST e aplicar EXATAMENTE o mesmo mapeamento `detail →
 * Error.message` do `api()`. Deixá-lo na `Studio.ui` era consequência de `ui.js` ser onde tudo
 * morava, não de coesão: o vizinho dele, `ui.drop()`, é drag&drop de verdade (classe `over`,
 * `<input type=file>`, listeners) e continua sendo da E2. Manter as duas cópias do mapeamento de
 * erro em frentes diferentes é a receita para elas divergirem na primeira mudança.
 *
 * **Contrato para a E2:** `Studio.ui.upload` deve REEXPORTAR esta função, não reimplementá-la — a
 * superfície de 28 membros da `Studio.ui` (recon §2) continua completa, com o mesmo nome e a mesma
 * assinatura, só que com uma implementação só.
 *
 * Nenhum `Content-Type` é enviado aqui, de propósito: o browser precisa gerar o `boundary` do
 * multipart. Este é o ponto em que o comportamento do `api()` (JSON sempre) NÃO se aplica.
 */
export async function apiUpload(
  url: string,
  files: ArrayLike<File> | Iterable<File>,
  field = "files",
  extra: CamposExtras = {},
): Promise<unknown> {
  const fd = new FormData();
  [...(files as Iterable<File>)].forEach((f) => fd.append(field, f));
  Object.entries(extra || {}).forEach(([k, v]) => {
    // `!== undefined && !== null` (não um truthy check): `0` e `""` são valores válidos e vão.
    if (v !== undefined && v !== null) fd.append(k, v instanceof Blob ? v : String(v));
  });
  const r = await fetch(url, { method: "POST", body: fd });
  // O corpo é lido ANTES do check de `ok` e o valor devolvido no sucesso é ESTE, não um segundo
  // `r.json()` — igual ao vanilla. Trocar a ordem faria um 200 com corpo não-JSON passar a lançar.
  const body: unknown = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = (body as CorpoDeErro)?.detail;
    const err = new Error((detail || r.statusText) as string) as ApiError;
    err.status = r.status;
    err.body = body;
    throw err;
  }
  return body;
}
