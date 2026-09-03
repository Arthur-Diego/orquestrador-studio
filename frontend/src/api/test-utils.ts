/**
 * Utilitários dos testes desta pasta. Não entra no bundle (só os `*.test.ts` importam).
 *
 * O `fetch` falso é tipado com a assinatura real do `fetch` de propósito: um `vi.fn(async () => …)`
 * sem parâmetros faz o `mock.calls` virar `[]` para o TypeScript, e aí toda inspeção do que foi
 * enviado (`calls[0][1].headers`) precisaria de `as any` — que é justamente o que estes testes
 * existem para não deixar passar.
 */
import { vi } from "vitest";

export type RespostaFalsa = {
  ok?: boolean;
  status?: number;
  statusText?: string;
  corpo?: unknown;
  /** Quando presente, `r.json()` rejeita — simula corpo que não é JSON. */
  textoCru?: string;
};

export type FetchFalso = ReturnType<typeof criarFetchFalso>;

export function criarFetchFalso(resp: RespostaFalsa = {}) {
  const { ok = true, status = 200, statusText = "OK", corpo, textoCru } = resp;
  return vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
    async () =>
      ({
        ok,
        status,
        statusText,
        json: async () => {
          if (textoCru !== undefined) throw new SyntaxError(`Unexpected token in JSON: ${textoCru}`);
          return corpo;
        },
      }) as unknown as Response,
  );
}

/** Instala o `fetch` falso como global e devolve o mock para inspeção. */
export function instalarFetch(resp: RespostaFalsa = {}): FetchFalso {
  const f = criarFetchFalso(resp);
  vi.stubGlobal("fetch", f);
  return f;
}

/** O `init` que chegou ao `fetch` na chamada `i`. */
export function initDaChamada(f: FetchFalso, i = 0): RequestInit {
  const chamada = f.mock.calls[i];
  if (!chamada) throw new Error(`fetch não foi chamado ${i + 1} vez(es)`);
  return chamada[1] ?? {};
}

/** A URL que chegou ao `fetch` na chamada `i`. */
export function urlDaChamada(f: FetchFalso, i = 0): string {
  const chamada = f.mock.calls[i];
  if (!chamada) throw new Error(`fetch não foi chamado ${i + 1} vez(es)`);
  return String(chamada[0]);
}
