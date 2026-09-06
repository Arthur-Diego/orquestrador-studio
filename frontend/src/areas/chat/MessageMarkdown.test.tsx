// Testes do markdown da bolha do assistente — Wave 11 · F01 (card #85).
//
// Os nove casos são os critérios de aceite da seção 9 do FDD
// (`docs/domains/chat/features/chat-markdown-fdd.md`). Os seis primeiros vêm do card.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Message } from "./ChatDock";
import { MessageMarkdown, srcPermitida, textoDoBloco } from "./MessageMarkdown";

function renderMd(texto: string, compact = false) {
  return render(<MessageMarkdown text={texto} compact={compact} />);
}

describe("MessageMarkdown", () => {
  it("1. negrito vira <strong> e não sobra asterisco na bolha", () => {
    const { container } = renderMd("Campanha **Café da Serra** (`cafe-serra`)");
    const strong = container.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong!.textContent).toBe("Café da Serra");
    expect(container.textContent).not.toContain("*");
    expect(container.querySelector("code")!.textContent).toBe("cafe-serra");
  });

  it("2. lista com hífen vira <ul> com um <li> por item", () => {
    const { container } = renderMd("- produto: café em grão\n- vibe: a encontrar");
    const itens = container.querySelectorAll("ul li");
    expect(itens).toHaveLength(1 + 1);
    expect(itens[0]!.textContent).toBe("produto: café em grão");
    expect(itens[1]!.textContent).toBe("vibe: a encontrar");
    expect(container.textContent).not.toContain("- ");
  });

  it("3. HTML cru não vira elemento nem executa (sem rehype-raw)", () => {
    const janela = window as unknown as { x?: number };
    delete janela.x;
    const { container } = renderMd("antes <b>oi</b> <script>window.x=1</script> depois");
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(janela.x).toBeUndefined();
    // O texto vizinho ao HTML descartado sobrevive.
    expect(container.textContent).toContain("antes");
    expect(container.textContent).toContain("depois");
  });

  it("4. link abre em nova aba com rel=noopener noreferrer", () => {
    const { container } = renderMd("[site](https://exemplo.com)");
    const a = container.querySelector("a");
    expect(a).not.toBeNull();
    expect(a!.getAttribute("href")).toBe("https://exemplo.com");
    expect(a!.getAttribute("target")).toBe("_blank");
    expect(a!.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("4b. href com protocolo perigoso é zerado pelo defaultUrlTransform", () => {
    const { container } = renderMd("[x](javascript:alert(1))");
    const a = container.querySelector("a")!;
    expect(a.getAttribute("href")).toBe("");
  });

  it("5. imagem externa não renderiza; imagem dos mounts do Studio renderiza", () => {
    const externa = renderMd("![x](https://exemplo.com/a.png)");
    expect(externa.container.querySelector("img")).toBeNull();
    externa.unmount();

    for (const url of ["/files/p1/base/x.png", "/mbfiles/p1/m.jpg", "/cfiles/ana/rosto.png"]) {
      const { container, unmount } = renderMd(`![base](${url})`);
      const img = container.querySelector("img");
      expect(img, url).not.toBeNull();
      expect(img!.getAttribute("src")).toBe(url);
      expect(img!.getAttribute("alt")).toBe("base");
      expect(img!.className).toBe("chat-md-img");
      unmount();
    }
  });

  it("5b. srcPermitida só aceita os três mounts estáticos do Studio", () => {
    expect(srcPermitida("/files/a.png")).toBe("/files/a.png");
    expect(srcPermitida("/mbfiles/a.png")).toBe("/mbfiles/a.png");
    expect(srcPermitida("/cfiles/a.png")).toBe("/cfiles/a.png");
    expect(srcPermitida("https://exemplo.com/files/a.png")).toBe("");
    expect(srcPermitida("//evil.example/files/a.png")).toBe("");
    expect(srcPermitida("/outra/a.png")).toBe("");
    expect(srcPermitida(undefined)).toBe("");
  });

  it("6. texto do usuário não passa pelo parser", () => {
    const noop = vi.fn();
    const { container } = render(
      <Message ev={{ kind: "user", text: "**a**" }} onAnswer={noop} onOpen={noop} done={false} />,
    );
    expect(container.querySelector("strong")).toBeNull();
    expect(container.querySelector(".chat-md")).toBeNull();
    expect(container.textContent).toContain("**a**");
    // A bolha do assistente, essa sim, é marcada como markdown.
    const assistente = render(
      <Message ev={{ kind: "assistant_text", text: "**a**" }} onAnswer={noop} onOpen={noop} done={false} />,
    );
    expect(assistente.container.querySelector('.chat-bubble[data-md="1"] strong')).not.toBeNull();
  });

  it("7. bloco de código vira pre > code.language-bash com CopyButton que copia o texto cru", async () => {
    const escrito: string[] = [];
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(async (t: string) => void escrito.push(t)) },
    });

    const { container } = renderMd("```bash\nmake verify\n```");
    const code = container.querySelector(".chat-md-code pre > code");
    expect(code).not.toBeNull();
    expect(code!.className).toContain("language-bash");
    expect(container.querySelector(".chat-md-code button.link.copy")).not.toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Copiar" }));
    expect(escrito).toEqual(["make verify"]);
  });

  it("7b. textoDoBloco é defensivo diante de hast inesperado", () => {
    expect(textoDoBloco(undefined)).toBe("");
    expect(textoDoBloco({})).toBe("");
    expect(textoDoBloco({ children: [] })).toBe("");
    expect(textoDoBloco({ children: [{ children: [{}] }] })).toBe("");
    expect(textoDoBloco({ children: [{ children: [{ value: "a\n" }] }] })).toBe("a");
  });

  it("8. markdown incompleto não lança e aparece literal", () => {
    expect(() => renderMd("**Camp")).not.toThrow();
    const { container } = renderMd("**Camp");
    expect(container.textContent).toContain("**Camp");
    // Texto vazio também não quebra: a bolha só fica sem conteúdo.
    const vazio = renderMd("");
    expect(vazio.container.querySelector(".chat-md")!.textContent).toBe("");
  });

  it("9. tool_result de erro renderiza markdown compacto; o de sucesso segue mudo", () => {
    const noop = vi.fn();
    const erro = render(
      <Message
        ev={{ kind: "tool_result", is_error: true, content: "**falhou**" }}
        onAnswer={noop}
        onOpen={noop}
        done={false}
      />,
    );
    const chip = erro.container.querySelector('.chat-tool[data-err="1"]')!;
    expect(chip.querySelector(".chat-md.compact strong")!.textContent).toBe("falhou");

    const ok = render(
      <Message
        ev={{ kind: "tool_result", is_error: false, content: "**ok**" }}
        onAnswer={noop}
        onOpen={noop}
        done={false}
      />,
    );
    expect(ok.container.innerHTML).toBe("");
  });
});
