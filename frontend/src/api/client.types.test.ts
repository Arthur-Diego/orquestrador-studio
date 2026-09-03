/**
 * Testes de TIPO. O que os prova é o `tsc --noEmit` do job `frontend`, não o runtime: cada
 * `@ts-expect-error` abaixo falha a build se aquela linha PARAR de dar erro de tipo.
 *
 * São eles que sustentam a afirmação "o contrato é tipado". Sem eles, uma mudança no `client.ts`
 * poderia afrouxar as restrições sem que nada acusasse — as chamadas continuariam compilando.
 */
import { describe, expect, it } from "vitest";

import { apiGet, apiPatch, apiPost, rota } from "./client";

describe("o contrato constrange de verdade (provado pelo tsc)", () => {
  it("aceita o que existe no /openapi.json", () => {
    const chamadas = [
      () => apiGet("/api/steps"),
      () => apiGet("/api/projects"),
      () => apiGet("/api/projects/{pid}/guide", { params: { pid: "p" } }),
      () => apiGet("/api/projects/{pid}/guide/{step}", { params: { pid: "p", step: "mood" } }),
      () => apiPost("/api/projects", { body: { name: "x" } }),
      () => apiPost("/api/projects", { body: { name: "x", product: "y", vibe: "z" } }),
      () => apiPatch("/api/projects/{pid}", { params: { pid: "p" }, body: { aspect_ratio: "1:1" } }),
      () => rota("/api/projects/{pid}/storyboard/scenes", { pid: "p" }),
    ];
    expect(chamadas).toHaveLength(8);
  });

  it("recusa o que não existe", () => {
    const recusadas = [
      // @ts-expect-error rota que não está no contrato
      () => apiGet("/api/nao-existe"),
      // @ts-expect-error erro de digitação na rota (falta o `s` de projects)
      () => apiGet("/api/project/{pid}/guide", { params: { pid: "p" } }),
      // @ts-expect-error `opcoes` é obrigatório porque a rota tem {pid}
      () => apiGet("/api/projects/{pid}/guide"),
      // @ts-expect-error faltou o parâmetro {step}
      () => apiGet("/api/projects/{pid}/guide/{step}", { params: { pid: "p" } }),
      // @ts-expect-error /api/steps não aceita POST
      () => apiPost("/api/steps"),
      // @ts-expect-error `nome` não existe no modelo NewProject (é `name`)
      () => apiPost("/api/projects", { body: { nome: "x" } }),
      // @ts-expect-error GET não tem corpo JSON no contrato
      () => apiGet("/api/steps", { body: { x: 1 } }),
      // @ts-expect-error parâmetro de rota que este template não tem
      () => rota("/api/steps", { pid: "p" }),
    ];
    expect(recusadas).toHaveLength(8);
  });
});
