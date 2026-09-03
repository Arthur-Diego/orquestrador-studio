/** Montagem de URL e de requisição a partir do contrato publicado. */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPatch, apiPost, request, resposta, rota } from "./client";
import { initDaChamada, instalarFetch, urlDaChamada } from "./test-utils";

const fetchOk = () => instalarFetch({ corpo: {} });

beforeEach(() => vi.unstubAllGlobals());

describe("rota()", () => {
  it("preenche os placeholders", () => {
    expect(rota("/api/projects/{pid}/guide/{step}", { pid: "2026-09-x", step: "mood" })).toBe(
      "/api/projects/2026-09-x/guide/mood",
    );
  });

  it("aplica encodeURIComponent, como o vanilla faz em cada chamada", () => {
    // O `app.js` escreve `encodeURIComponent(pid)` ~200 vezes; centralizar aqui é o ponto.
    expect(rota("/api/projects/{pid}", { pid: "a/b c" })).toBe("/api/projects/a%2Fb%20c");
  });

  it("explode em vez de mandar um `undefined` na URL", () => {
    // O compilador já barra a chave FALTANDO (ver `client.types.test.ts`); esta é a rede para o
    // valor que chega `undefined` em runtime — um `pid` de estado ainda não carregado, por exemplo.
    const semPid = { pid: undefined } as unknown as { pid: string };
    expect(() => rota("/api/projects/{pid}", semPid)).toThrow(/parâmetro ausente/);
  });

  it("template sem placeholder passa intacto", () => {
    expect(rota("/api/steps")).toBe("/api/steps");
  });
});

describe("request()", () => {
  it("GET não manda `method` — é `api(path)` sem opts, igual ao vanilla", async () => {
    const f = fetchOk();
    await apiGet("/api/steps");
    expect(initDaChamada(f)).toEqual({ headers: { "Content-Type": "application/json" } });
  });

  it("POST serializa o corpo e manda o método em maiúsculas", async () => {
    const f = fetchOk();
    await apiPost("/api/projects", { body: { name: "Campanha" } });
    const init = initDaChamada(f);
    expect(urlDaChamada(f)).toBe("/api/projects");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"name":"Campanha"}');
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("PATCH em rota com parâmetro", async () => {
    const f = fetchOk();
    await apiPatch("/api/projects/{pid}", { params: { pid: "p1" }, body: { aspect_ratio: "9:16" } });
    expect(urlDaChamada(f)).toBe("/api/projects/p1");
    expect(initDaChamada(f).method).toBe("PATCH");
  });

  it("query: omite undefined/null e serializa booleano como 1/0 (convenção do vanilla)", async () => {
    const f = fetchOk();
    await apiGet("/api/higgsfield/status", { query: { refresh: true } });
    expect(urlDaChamada(f)).toBe("/api/higgsfield/status?refresh=1");

    const g = fetchOk();
    await apiGet("/api/higgsfield/status", { query: {} });
    expect(urlDaChamada(g)).toBe("/api/higgsfield/status");
  });

  it("`init` é repassado e pode sobrepor o que o request montou", async () => {
    const f = fetchOk();
    await request("post", "/api/projects/{pid}/reset", {
      params: { pid: "p" },
      init: { cache: "no-store" },
    });
    expect(initDaChamada(f).cache).toBe("no-store");
  });
});

describe("resposta()", () => {
  it("é asserção, não validação: não toca o valor em runtime", async () => {
    fetchOk();
    const alvo = { qualquer: "coisa" };
    await expect(resposta<{ qualquer: string }>(Promise.resolve(alvo))).resolves.toBe(alvo);
  });
});
