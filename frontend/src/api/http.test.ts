/**
 * Teste DIFERENCIAL do client HTTP: o helper `api()` do vanilla é copiado aqui, verbatim, e serve
 * de oráculo. Cada caso roda nos dois e exige o mesmo resultado observável — os argumentos que
 * chegam ao `fetch` e a `message` do erro lançado.
 *
 * É a técnica certa para uma migração de tecnologia: um teste que só afirmasse "a mensagem é
 * `detail`" passaria com uma implementação que usa `??` no lugar de `||`, ou que faz merge de
 * headers em vez de substituir. Comparar contra o original pega isso.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, apiUpload, isApiError, type ApiError } from "./http";
import { initDaChamada, instalarFetch, type RespostaFalsa } from "./test-utils";

/**
 * O ORÁCULO — `studio/web/app.js:17-21`, copiado sem uma alteração:
 *
 * ```js
 * const api = async (path, opts = {}) => {
 *   const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
 *   if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
 *   return r.json();
 * };
 * ```
 */
const apiVanilla = async (path: string, opts: RequestInit = {}): Promise<unknown> => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  if (!r.ok) throw new Error(((await r.json().catch(() => ({}))) as any).detail || r.statusText);
  return r.json();
};

type Resposta = RespostaFalsa;
const instalar = instalarFetch;

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("api() — o que chega ao fetch", () => {
  it("manda Content-Type: application/json inclusive em GET (sim, de propósito)", async () => {
    const f = instalar({ corpo: { ok: 1 } });
    await api("/api/steps");
    expect(f).toHaveBeenCalledWith("/api/steps", { headers: { "Content-Type": "application/json" } });

    const g = instalar({ corpo: { ok: 1 } });
    await apiVanilla("/api/steps");
    expect(f.mock.calls[0]).toEqual(g.mock.calls[0]);
  });

  it("o spread de opts vem DEPOIS do headers: quem passa headers substitui o Content-Type", async () => {
    const opts: RequestInit = { method: "POST", headers: { "X-Meu": "1" }, body: "{}" };
    const f = instalar({ corpo: {} });
    await api("/r", opts);
    const g = instalar({ corpo: {} });
    await apiVanilla("/r", opts);

    expect(f.mock.calls[0]).toEqual(g.mock.calls[0]);
    // e o que isso significa, explicitamente: o Content-Type SUMIU, não foi mesclado.
    expect(initDaChamada(f).headers).toEqual({ "X-Meu": "1" });
  });

  it("devolve o JSON do corpo no sucesso", async () => {
    instalar({ corpo: [{ id: "refs" }] });
    await expect(api("/api/steps")).resolves.toEqual([{ id: "refs" }]);
  });
});

describe("api() — mapeamento de erro (o texto vai para o toast: ADR-004 o congela)", () => {
  const casos: { nome: string; resp: Resposta; esperado: string }[] = [
    {
      nome: "detail do FastAPI vence o statusText",
      resp: { ok: false, status: 404, statusText: "Not Found", corpo: { detail: "projeto não encontrado: x" } },
      esperado: "projeto não encontrado: x",
    },
    {
      nome: "sem detail, cai no statusText",
      resp: { ok: false, status: 500, statusText: "Internal Server Error", corpo: {} },
      esperado: "Internal Server Error",
    },
    {
      nome: "detail vazio cai no statusText — é `||`, não `??`",
      resp: { ok: false, status: 400, statusText: "Bad Request", corpo: { detail: "" } },
      esperado: "Bad Request",
    },
    {
      nome: "corpo que não é JSON cai no statusText",
      resp: { ok: false, status: 502, statusText: "Bad Gateway", textoCru: "<html>" },
      esperado: "Bad Gateway",
    },
    {
      nome: "409 do gate de login do Higgsfield",
      resp: {
        ok: false,
        status: 409,
        statusText: "Conflict",
        corpo: { detail: "Higgsfield CLI sem login (higgsfield auth login)", installed: true },
      },
      esperado: "Higgsfield CLI sem login (higgsfield auth login)",
    },
    {
      nome: "422 do Pydantic: detail é lista, e a coerção do JS é a mesma dos dois lados",
      resp: {
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        corpo: { detail: [{ loc: ["body", "name"], msg: "field required" }] },
      },
      esperado: "[object Object]",
    },
  ];

  for (const { nome, resp, esperado } of casos) {
    it(nome, async () => {
      instalar(resp);
      const meu = (await api("/r").catch((e: unknown) => e)) as Error;
      instalar(resp);
      const dele = (await apiVanilla("/r").catch((e: unknown) => e)) as Error;

      expect(meu.message).toBe(esperado);
      expect(meu.message).toBe(dele.message);
      expect(meu).toBeInstanceOf(Error);
      // `name` continua "Error": uma subclasse `ApiError` mudaria isto, e `err.name` é observável.
      expect(meu.name).toBe("Error");
      expect(meu.name).toBe(dele.name);
    });
  }

  it("acrescenta status e body ao erro — adição pura, o vanilla os descartava", async () => {
    instalar({ ok: false, status: 409, statusText: "Conflict", corpo: { detail: "sem login", installed: false } });
    const e = (await api("/r").catch((x: unknown) => x)) as ApiError;
    expect(isApiError(e)).toBe(true);
    expect(e.status).toBe(409);
    expect(e.body).toEqual({ detail: "sem login", installed: false });
  });
});

describe("apiUpload() — o `Studio.ui.upload` do vanilla", () => {
  it("monta o FormData com o campo pedido e omite só undefined/null", async () => {
    const f = instalar({ corpo: { ok: true } });
    const a = new File(["a"], "a.png", { type: "image/png" });
    const b = new File(["b"], "b.png", { type: "image/png" });

    await apiUpload("/api/projects/p/refs/import/upload", [a, b], "files", {
      kind: "ref",
      // `0` e `""` são valores VÁLIDOS e têm de ir: o vanilla testa `!== undefined && !== null`.
      indice: 0,
      nota: "",
      ausente: undefined,
      nulo: null,
    });

    const init = initDaChamada(f);
    expect(init.method).toBe("POST");
    // Nenhum Content-Type: o browser precisa gerar o boundary do multipart.
    expect(init.headers).toBeUndefined();
    const fd = init.body as FormData;
    expect(fd.getAll("files")).toHaveLength(2);
    expect(fd.get("kind")).toBe("ref");
    expect(fd.get("indice")).toBe("0");
    expect(fd.get("nota")).toBe("");
    expect(fd.has("ausente")).toBe(false);
    expect(fd.has("nulo")).toBe(false);
  });

  it("mapeia o erro igual ao api(): detail → message, com status e body", async () => {
    instalar({ ok: false, status: 413, statusText: "Payload Too Large", corpo: { detail: "arquivo grande demais" } });
    const e = (await apiUpload("/u", []).catch((x: unknown) => x)) as ApiError;
    expect(e.message).toBe("arquivo grande demais");
    expect(e.status).toBe(413);
  });

  it("no sucesso devolve o corpo já lido, não um segundo r.json()", async () => {
    instalar({ corpo: { saved: 2 } });
    await expect(apiUpload("/u", [])).resolves.toEqual({ saved: 2 });
  });
});
