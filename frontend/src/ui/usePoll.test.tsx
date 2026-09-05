// Wave 10 · E2 — `poll` (porte do `Studio.ui.poll`) e `usePoll` (ciclo de vida React).
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { poll, usePoll } from "./usePoll";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

afterEach(cleanup);

describe("poll", () => {
  it("para quando `fn` devolve false", async () => {
    let calls = 0;
    poll(() => {
      calls += 1;
      return calls >= 2 ? false : undefined;
    }, 1);
    await sleep(40);
    expect(calls).toBe(2);
  });

  it("para após 3 erros seguidos", async () => {
    let calls = 0;
    poll(() => {
      calls += 1;
      throw new Error("falha");
    }, 1);
    await sleep(40);
    expect(calls).toBe(3);
  });

  it("stop() interrompe antes do próximo tick", async () => {
    let calls = 0;
    const h = poll(() => {
      calls += 1;
    }, 1);
    h.stop();
    await sleep(20);
    expect(calls).toBeLessThanOrEqual(1);
  });
});

describe("usePoll", () => {
  it("desliga sozinho no unmount", async () => {
    let calls = 0;
    function C() {
      usePoll(() => {
        calls += 1;
      }, 1, true);
      return null;
    }
    const { unmount } = render(<C />);
    await sleep(20);
    const meio = calls;
    expect(meio).toBeGreaterThanOrEqual(1);
    unmount();
    await sleep(20);
    expect(calls).toBe(meio);
  });

  it("não liga quando `enabled` é false", async () => {
    let calls = 0;
    function C() {
      usePoll(() => {
        calls += 1;
      }, 1, false);
      return null;
    }
    render(<C />);
    await sleep(20);
    expect(calls).toBe(0);
  });
});
