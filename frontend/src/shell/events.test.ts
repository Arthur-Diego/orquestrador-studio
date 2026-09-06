// Barramento de mudanças do shell — UT-10…UT-14 do `_tests.md` (Wave 11 · F03, card #87).
//
// Temporizadores FALSOS em toda a suíte: a janela de debounce é de 400 ms e nenhum teste pode
// depender de `setTimeout` real (ADR-008 — testes rápidos, sem rede e sem navegador).
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEBOUNCE_GUIA_MS } from "../api/guide-sync";
import { emitNavIntent, emitStudioChange, useNavIntent, useStudioChange } from "./events";
import type { MudancaDoStudio, NavIntent } from "./events";

/** Atalho: o evento que o `ChatDock` publica a partir de um `state_changed` do WebSocket. */
function mudanca(pid: string | null, step: string, tool = "refs_search"): MudancaDoStudio {
  return { pid, step, scope: "job", tool };
}

describe("useStudioChange — filtro por step e por pid (UT-10)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("chama cb uma vez para o próprio step e o próprio pid", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(mudanca("p1", "refs"));
  });

  it("não chama para evento de OUTRA campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p2", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });

  it("não chama para evento de OUTRA etapa", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "base"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });

  it("assinante sem pid declarado (área global) aceita qualquer campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb));

    emitStudioChange({ pid: "p9", step: "characters", scope: "selection", tool: "character_apply" });
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("assinante que declarou pid null (tela sem campanha) ignora evento de campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: null }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });
});

describe("useStudioChange — debounce de 400 ms, o último vence (UT-11)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("três eventos do mesmo (pid, step) na janela viram UMA chamada, com o último", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("base", cb, { pid: "p1" }));

    emitStudioChange({ pid: "p1", step: "base", scope: "job", tool: "base_generate" });
    vi.advanceTimersByTime(100);
    emitStudioChange({ pid: "p1", step: "base", scope: "candidates", tool: "job_wait" });
    vi.advanceTimersByTime(100);
    emitStudioChange({ pid: "p1", step: "base", scope: "selection", tool: "base_pick" });

    // Ainda dentro da janela do terceiro evento: nada rodou.
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS - 1);
    expect(cb).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith({ pid: "p1", step: "base", scope: "selection", tool: "base_pick" });
  });

  it("opts.debounceMs sobrescreve a janela default", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("mood", cb, { pid: "p1", debounceMs: 50 }));

    emitStudioChange(mudanca("p1", "mood", "mood_generate"));
    vi.advanceTimersByTime(50);

    expect(cb).toHaveBeenCalledTimes(1);
  });
});

describe("useStudioChange — mudança global chega a todos (UT-12)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("evento com pid null chega a um assinante que declarou pid p1", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb, { pid: "p1" }));

    const global: MudancaDoStudio = {
      pid: null,
      step: "characters",
      scope: "candidates",
      tool: "character_wait",
    };
    emitStudioChange(global);
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(global);
  });
});

describe("useStudioChange — unmount cancela o timer pendente (UT-13)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("desmontar antes do fim do debounce não chama cb", () => {
    const cb = vi.fn();
    const { unmount } = renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS - 1);
    unmount();
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS * 10);

    expect(cb).not.toHaveBeenCalled();
  });

  it("depois do unmount o assinante sai do barramento e não recebe mais nada", () => {
    const cb = vi.fn();
    const { unmount } = renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));
    unmount();

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });
});

describe("emitStudioChange — assinante que lança não cala os demais (UT-14)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("o throw de um assinante não impede o outro assinante do mesmo step de receber", () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const explode = vi.fn(() => {
      throw new Error("tela quebrada");
    });
    const ok = vi.fn();
    renderHook(() => useStudioChange("refs", explode, { pid: "p1" }));
    renderHook(() => useStudioChange("refs", ok, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(explode).toHaveBeenCalledTimes(1);
    expect(ok).toHaveBeenCalledTimes(1);
    // O erro não é engolido em silêncio: deixa rastro no console de desenvolvimento.
    expect(erro).toHaveBeenCalled();
  });
});

// UT-20 — o debounce é por par `(pid do evento, step)`, e não por assinante (§5 Contrato 4 e §6 do
// FDD). Só o assinante GLOBAL distingue os dois casos, porque só ele recebe mais de uma campanha.
// Apontado pelo fiscal de fechamento de ciclo (divergência D1) e corrigido no código, não na spec.
describe("useStudioChange — debounce por par (pid do evento, step) (UT-20)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("assinante global recebe DUAS campanhas da mesma janela, uma chamada cada", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb));

    // Duas campanhas dentro da MESMA janela de 400 ms: com um timer por assinante, o evento de p1
    // seria perdido (não adiado) — que é exatamente a regressão que este teste tranca.
    emitStudioChange(mudanca("p1", "characters", "character_apply"));
    emitStudioChange(mudanca("p2", "characters", "character_apply"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(2);
    expect(cb.mock.calls.map((c) => (c[0] as MudancaDoStudio).pid).sort()).toEqual(["p1", "p2"]);
  });

  it("a mudança global tem janela própria e não engole a de uma campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb));

    emitStudioChange(mudanca("p1", "characters", "character_apply"));
    emitStudioChange(mudanca(null, "characters", "character_wait"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(2);
    expect(cb.mock.calls.map((c) => (c[0] as MudancaDoStudio).tool).sort()).toEqual([
      "character_apply",
      "character_wait",
    ]);
  });

  it("dentro de UMA campanha o colapso continua valendo: 3 eventos → 1 chamada", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb));

    emitStudioChange(mudanca("p1", "characters", "character_create"));
    emitStudioChange(mudanca("p1", "characters", "character_explore"));
    emitStudioChange(mudanca("p1", "characters", "character_pick"));
    emitStudioChange(mudanca("p2", "characters", "character_apply"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(2); // uma por campanha, não uma por evento
    expect(cb).toHaveBeenCalledWith(mudanca("p1", "characters", "character_pick")); // o último vence
  });

  it("unmount cancela TODAS as janelas abertas do assinante global", () => {
    const cb = vi.fn();
    const { unmount } = renderHook(() => useStudioChange("characters", cb));

    emitStudioChange(mudanca("p1", "characters"));
    emitStudioChange(mudanca("p2", "characters"));
    unmount();
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS * 3);

    expect(cb).not.toHaveBeenCalled();
  });
});

// UT-28…UT-32 do `_tests.md` (Wave 11 · F08, card #88): o barramento de INTENÇÃO DE ABERTURA.
//
// `useNavIntent` tem prefixo `use` porque é o nome publicado no Contrato 6 do FDD, mas não é um hook
// React (nem estado, nem efeito — ver o comentário no `events.ts`). Chamá-la direto de dentro de um
// `it` é o uso previsto, e é o que o `rules-of-hooks` não tem como saber.
/* eslint-disable react-hooks/rules-of-hooks */
describe("emitNavIntent/useNavIntent — intenção sticky de um disparo (UT-28…UT-31)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    // Nenhum teste pode deixar intenção retida para o seguinte: consumir é a única forma de limpar.
    useNavIntent("storyboard", () => {});
    useNavIntent("mood", () => {});
    vi.useRealTimers();
  });

  const intencao = (target: string, params: Record<string, unknown> = {}): NavIntent => ({
    pid: "campanha-a",
    target,
    params,
    askId: "9f2c",
  });

  it("UT-28 publica e o consumidor do mesmo target recebe uma vez", () => {
    const cb = vi.fn();
    const i = intencao("storyboard", { scene: "cena02" });

    emitNavIntent(i);
    useNavIntent("storyboard", cb);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(i);
  });

  it("UT-29 consumir limpa: o segundo consumidor não recebe nada", () => {
    const cb1 = vi.fn();
    const cb2 = vi.fn();

    emitNavIntent(intencao("storyboard", { scene: "cena02" }));
    useNavIntent("storyboard", cb1);
    useNavIntent("storyboard", cb2);

    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).not.toHaveBeenCalled();
  });

  it("UT-30 consumidor de outro target não consome e deixa a intenção intacta", () => {
    const errado = vi.fn();
    const certo = vi.fn();
    const i = intencao("storyboard", { scene: "cena02" });

    emitNavIntent(i);
    useNavIntent("mood", errado);
    expect(errado).not.toHaveBeenCalled();

    useNavIntent("storyboard", certo);
    expect(certo).toHaveBeenCalledTimes(1);
    expect(certo).toHaveBeenCalledWith(i);
  });

  it("UT-31 publicar duas vezes antes do consumo mantém só a última", () => {
    const cb = vi.fn();
    const ultima = intencao("storyboard", { scene: "cena05" });

    emitNavIntent(intencao("storyboard", { scene: "cena02" }));
    emitNavIntent(ultima);
    useNavIntent("storyboard", cb);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(ultima);
    // E a fila não existe: depois do consumo não sobra a primeira.
    const depois = vi.fn();
    useNavIntent("storyboard", depois);
    expect(depois).not.toHaveBeenCalled();
  });

  it("sem intenção publicada, consumir não chama ninguém", () => {
    const cb = vi.fn();
    useNavIntent("storyboard", cb);
    expect(cb).not.toHaveBeenCalled();
  });

  it("intenção sem askId e sem params é válida (a tela alvo só quer saber que foi pedida)", () => {
    const cb = vi.fn();
    const i: NavIntent = { pid: null, target: "moodboards", params: {} };

    emitNavIntent(i);
    useNavIntent("moodboards", cb);

    expect(cb).toHaveBeenCalledWith(i);
  });
});

describe("UT-32 os dois barramentos são independentes", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("publicar intenção não dispara assinante de mudança, e vice-versa", () => {
    const daMudanca = vi.fn();
    const daIntencao = vi.fn();
    renderHook(() => useStudioChange("storyboard", daMudanca, { pid: "p1" }));

    emitNavIntent({ pid: "p1", target: "storyboard", params: { scene: "cena02" } });
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(daMudanca).not.toHaveBeenCalled();

    emitStudioChange({ pid: "p1", step: "storyboard", scope: "job" });
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(daMudanca).toHaveBeenCalledTimes(1);

    // A intenção seguiu retida o tempo todo: o barramento de mudanças não a consumiu.
    useNavIntent("storyboard", daIntencao);
    expect(daIntencao).toHaveBeenCalledTimes(1);
  });
});
