"""Dump de `textContent` de todas as telas — oráculo do ADR-004 na Wave 10 (migração React).

    . .qa/runs/<run-id>/env.sh
    python scripts/qa/textcontent.py --run <run-id> --saida docs/qa/reports/<data>-<run>/textcontent

A Wave 10 é refatoração pura: o framework de frontend muda, o comportamento não. O critério mais
difícil de verificar por leitura é o do ADR-004 — *nenhum texto visível ao usuário muda*, porque
todo texto de tela é conteúdo de aula. Este script transforma esse critério em `diff`.

## O que é capturado

Para cada tela, os **nós de texto** de `.app` (sidebar + topbar + `#main`) em **ordem de
documento**, um por linha, com espaço em branco normalizado. Isto é `textContent`, não `innerText`:
texto escondido por CSS entra também — o que é proposital, porque um texto de aula que só aparece
num estado posterior da tela continua sendo texto de aula.

Cada tela de etapa é capturada duas vezes, com a campanha **cheia** e com a **vazia**, porque os
textos de empty-state ("sem imagens ainda", "Sem campanha selecionada…") são conteúdo de aula tanto
quanto o resto.

## Por que texto puro, sem seletor nem estrutura

A migração **vai** reorganizar a árvore do DOM — é o objetivo dela. Um dump que carregasse o
caminho CSS de cada string acusaria diferença em toda frente, mesmo quando nenhuma palavra mudasse,
e o oráculo viraria ruído. A lista ordenada de textos é robusta à reestruturação e sensível
exatamente ao que o ADR-004 protege.

## Como comparar (é isto que as frentes E1…E10 rodam)

    make qa-up qa-seed RUN=<frente>
    . .qa/runs/<frente>/env.sh
    python scripts/qa/textcontent.py --run <frente> --saida /tmp/tc-<frente>
    diff -ru docs/qa/reports/2026-09-03-react-e0-v2/textcontent /tmp/tc-<frente>

Saída vazia = critério 5 da definição de pronto atendido. Qualquer linha de diferença é um texto
que mudou e precisa de justificativa — ou é bug da migração.

`MANIFEST.txt` traz o sha256 e a contagem de linhas de cada arquivo, para conferência rápida sem
rodar o diff inteiro.

## Limite conhecido

Captura o **estado de repouso** de cada tela: o que está no DOM depois de abrir e a tela assentar.
Texto que só existe dentro de um modal aberto por interação (folha de custo, modal de progresso)
não entra aqui — esse é território dos 382 cenários Playwright, que exercitam a interação.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.qa import harness as H  # noqa: E402

#: Nós de texto de `.app`, em ordem de documento, com espaço em branco normalizado.
#: `<script>`/`<style>` ficam de fora: são código, não texto de tela.
COLETA_JS = """
() => {
  const raiz = document.querySelector('.app') || document.body;
  const it = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      const pai = n.parentElement;
      if (!pai) return NodeFilter.FILTER_REJECT;
      const tag = pai.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEMPLATE') return NodeFilter.FILTER_REJECT;
      return /\\S/.test(n.nodeValue || '') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  const out = [];
  let n;
  while ((n = it.nextNode())) out.push(n.nodeValue.replace(/\\s+/g, ' ').trim());
  return out;
}
"""


def coletar(page, ctx: H.Ctx, tela: str, pid: str | None) -> list[str]:
    H.abrir_tela(page, ctx, tela, pid, forcar=True)
    return page.evaluate(COLETA_JS)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--run", required=True, help="run-id (pasta em .qa/runs/)")
    p.add_argument("--repo", default=str(REPO))
    p.add_argument("--saida", required=True, help="diretório do dump")
    p.add_argument("--telas", nargs="*", default=None)
    a = p.parse_args(argv)

    run_dir = Path(a.repo) / ".qa" / "runs" / a.run
    if not (run_dir / "seed.json").exists():
        print(f"seed.json ausente em {run_dir} — rode stack-up.sh e seed.sh", file=sys.stderr)
        return 2
    ctx = H.Ctx.da_rodada(run_dir)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    nav = H.Navegador(ctx, headless=True)
    page, _ = nav.nova_pagina("light", (1440, 900))
    page.goto(f"{ctx.base}/")
    H.esperar_tela(page)
    ctx.steps = page.request.get(f"{ctx.base}/api/steps").json()

    etapas = [s["id"] for s in ctx.steps if s["status"] == "ready"]
    todas = ["shell", "overview", *etapas, "moodboards", "creditos"]
    telas = [t for t in todas if not a.telas or t in a.telas]

    manifesto: list[str] = []
    try:
        for tela in telas:
            # Área global não tem campanha; tela de etapa é capturada cheia E vazia (empty-state
            # também é texto de aula).
            variantes: list[tuple[str, str | None]] = (
                [("", None)] if tela in ("moodboards", "creditos")
                else [("", ctx.pid_cheio)] + ([("--vazio", ctx.pid_vazio)] if tela not in ("shell",) else [])
            )
            for sufixo, pid in variantes:
                linhas = coletar(page, ctx, tela, pid)
                corpo = "\n".join(linhas) + "\n"
                arq = saida / f"{tela}{sufixo}.txt"
                arq.write_text(corpo, encoding="utf-8")
                sha = hashlib.sha256(corpo.encode("utf-8")).hexdigest()
                manifesto.append(f"{sha}  {len(linhas):5d}  {arq.name}")
                print(f"{arq.name}: {len(linhas)} nós de texto")
    finally:
        nav.fechar()

    (saida / "MANIFEST.txt").write_text(
        "# sha256(arquivo)  nós-de-texto  arquivo\n"
        "# Dump de textContent — oráculo do ADR-004 (Wave 10). Reproduza com:\n"
        "#   python scripts/qa/textcontent.py --run <frente> --saida /tmp/tc && diff -ru <este-dir> /tmp/tc\n"
        + "\n".join(sorted(manifesto)) + "\n", encoding="utf-8")
    print(f"\n{len(manifesto)} arquivos em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
