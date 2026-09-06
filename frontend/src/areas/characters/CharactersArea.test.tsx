// Personagens × barramento de mudanças do chat — Wave 11 · frente F03 (card #87,
// ADH-OS-20260906-05), rodada de review 001 / issue_001. `[extensão]`
//
// O que se prova aqui: as DUAS telas da área reagem ao `state_changed` de `characters`. A lista já
// reagia; a ficha (`CharacterDetail`) não, e ela é justamente a que mostra o artefato das tools de
// personagem. O poll interno da ficha é condicionado a `busy`, que só liga quando a PRÓPRIA tela
// disparou o job — então um `character_explore` vindo do chat deixava a ficha aberta congelada até
// o usuário sair e voltar, o defeito do card #87 uma tela mais fundo.
//
// Sem rede e sem navegador (ADR-008): `fetch` é falso e o barramento é o de verdade (UT-10…UT-14
// já provam o barramento; o que se prova aqui é que a tela ASSINA e recarrega).
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ShellProvider } from "../../shell/context";
import { mockShellApi } from "../../shell/test-utils";
import { emitStudioChange } from "../../shell/events";
import { CharactersArea } from "./CharactersArea";

const PERSONAGEM = { id: "eden", name: "Eden", style: "foto", locked_ref: null };

/** Caminhos pedidos ao backend, na ordem — é a contagem deles que prova a recarga. */
let pedidos: string[] = [];
/** Estado do job da ficha; cada teste ajusta antes de emitir a mudança. */
let jobState = "idle";

beforeEach(() => {
  pedidos = [];
  jobState = "idle";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).replace(/^https?:\/\/[^/]+/, "");
      pedidos.push(path);
      const corpo = path === "/api/characters"
        ? [PERSONAGEM]
        : path.endsWith("/job")
          ? { state: jobState, done: 0, total: 6, added: 0 }
          : path.includes("/candidates")
            ? []
            : PERSONAGEM;
      return { ok: true, status: 200, statusText: "OK", json: async () => corpo } as unknown as Response;
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function montar() {
  return render(
    <ShellProvider value={mockShellApi()}>
      <CharactersArea pid="p1" />
    </ShellProvider>,
  );
}

/** Publica a mudança que o `character_wait` produz: global, sem pid (Contrato 1 da §5 do FDD). */
function mudancaDePersonagem(scope: "candidates" | "library" | "job" = "candidates") {
  act(() => emitStudioChange({ pid: null, step: "characters", scope, tool: "character_wait" }));
}

/** O debounce do barramento é de 400 ms — esperar a janela é parte do contrato. */
async function esperarODebounce(condicao: () => void) {
  await waitFor(condicao, { timeout: 2000 });
}

describe("CharactersArea — barramento de mudanças do chat", () => {
  it("a lista recarrega ao receber a mudança global de characters", async () => {
    montar();
    await screen.findByText("Eden");
    const antes = pedidos.filter((p) => p === "/api/characters").length;

    mudancaDePersonagem("library");

    await esperarODebounce(() =>
      expect(pedidos.filter((p) => p === "/api/characters").length).toBeGreaterThan(antes),
    );
  });

  it("a FICHA aberta recarrega ao receber a mudança (issue_001)", async () => {
    montar();
    fireEvent.click(await screen.findByText("Eden"));
    await waitFor(() => expect(pedidos.some((p) => p === "/api/characters/eden")).toBe(true));
    const antes = pedidos.filter((p) => p === "/api/characters/eden").length;

    mudancaDePersonagem();

    await esperarODebounce(() =>
      expect(pedidos.filter((p) => p === "/api/characters/eden").length).toBeGreaterThan(antes),
    );
  });

  it("a ficha religa o poll quando o job disparado POR FORA ainda está running", async () => {
    montar();
    fireEvent.click(await screen.findByText("Eden"));
    await waitFor(() => expect(pedidos.some((p) => p === "/api/characters/eden")).toBe(true));

    // O chat disparou `character_explore`: o job está rodando e esta tela não sabe (busy === false).
    jobState = "running";
    mudancaDePersonagem("job");

    // A ficha lê o job do personagem — é essa leitura que decide religar o `setInterval` existente.
    await esperarODebounce(() =>
      expect(pedidos.some((p) => p === "/api/characters/eden/job")).toBe(true),
    );
  });
});
