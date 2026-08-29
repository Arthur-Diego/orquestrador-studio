"""Gera as seções determinísticas do relatório de uma rodada (skill qa-studio, Passo 6).

    python scripts/qa/relatorio.py --run <run-id> [--saida docs/qa/reports/<data>-<run>/relatorio.md]

Lê `resultados.json`, `api.json` e `check-env.txt` (se existir) de `.qa/runs/<run-id>/` e escreve o
esqueleto do relatório seguindo `.claude/skills/qa-studio/references/relatorio-template.md`:
seções 2, 3, 4 e 6 preenchidas; seções 1, 5, 7, 8 e 9 vêm com marcadores `<…>` para o agente
completar (identificação, inspeção visual, apontamentos, veredito, histórico). Se o arquivo de
saída já existir, só as seções geradas são substituídas (as manuais ficam intactas).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CABECALHO = """# QA E2E — <escopo> — {data} — {run}

## 1. Identificação

| Campo | Valor |
| --- | --- |
| Card-pai (Trello) | <URL> |
| Task-Id | <ADH-OS-…> |
| Branch / worktree | <fix/qa-…> · <caminho> |
| Commit base (develop) | <sha> |
| Modo | {modo} |
| Base URL | {base} |
| Telas pedidas / executadas | {telas} |
| Rodadas executadas | <n> de <--rodadas> |
| Executado por | qa-studio |
"""

MANUAIS = {
    "5": "## 5. Inspeção visual (feita pelo agente sobre os prints)\n\n| Tela | Tema | Observação | Severidade | Print |\n| --- | --- | --- | --- | --- |\n| <tela> | <tema> | <observação verificável> | ALTA / MEDIA / BAIXA | <caminho> |\n",
    "7": "## 7. Apontamentos\n\n| # | Severidade | Dono | Tela/rota | Descrição objetiva | Caso de origem | Destino | Card |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| AP-01 | <…> | <…> | <…> | <…> | <…> | <…> | <URL> |\n",
    "8": "## 8. Veredito\n\n- Casos: {n_pass} PASSA, {n_fail} FALHA, {n_blq} BLOQUEADO de {n}.\n- Apontamentos: <A> ALTA, <M> MEDIA, <B> BAIXA — <c> corrigidos, <k> em cards abertos, <h> aguardando decisão humana.\n- Situação: <APROVADA | APROVADA COM RESSALVAS | REPROVADA>.\n- PR: <URL>.\n",
    "9": "## 9. Histórico de rodadas\n\n### Rodada 1 — <data hora>\n- Executado: <telas>, {n} casos, auditoria de API, newman.\n- Apontamentos abertos: <AP-…>.\n",
}


def secao_ambiente(run_dir: Path) -> str:
    p = run_dir / "check-env.txt"
    txt = p.read_text().strip() if p.exists() else "<colar a saída do check-env.sh>"
    return "## 2. Ambiente (saída real do check-env.sh)\n\n```text\n" + txt + "\n```\n"


def secao_casos(res: dict) -> str:
    linhas = ["## 3. Casos executados", "", "| # | Tela | Cenário | Resultado | Evidência |", "| --- | --- | --- | --- | --- |"]
    for c in res.get("casos", []):
        ev = c["evidencias"][0] if c.get("evidencias") else (c.get("detalhe", "")[:120].replace("|", "\\|").replace("\n", " ") or "—")
        if c["status"] != "PASSA" and c.get("detalhe"):
            ev = (c["evidencias"][0] + " — " if c.get("evidencias") else "") + c["detalhe"][:160].replace("|", "\\|").replace("\n", " ")
        linhas.append(f"| {c['id']} | {c['tela']} | {c['titulo'].replace('|', '\\|')} | {c['status']} | {ev} |")
    return "\n".join(linhas) + "\n"


def secao_auditoria(res: dict) -> str:
    linhas = ["## 4. Auditoria automática por tela (tema × viewport)", "",
              "| Tela | Tema | Viewport | Problemas | Console/pageerror | HTTP ≥ 400 | Print |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for a in res.get("auditorias", []):
        probs = "; ".join(a.get("problemas", [])) or ("erro: " + a["erro"] if a.get("erro") else "—")
        cons = len(a.get("pageerrors", [])) + len(a.get("console", []))
        http = "; ".join(f"{h['status']} {h['method']} {h['url']}" for h in a.get("http_erros", [])[:4]) or "—"
        linhas.append(f"| {a['tela']} | {a['tema']} | {a['viewport']} | {probs.replace('|', '\\|')} | {cons or '—'} | {http} | {a.get('print', '—')} |")
    timers = {k: v for k, v in res.get("timers", {}).items() if v}
    linhas += ["", f"Timers órfãos: {timers if timers else '—'}.", ""]
    return "\n".join(linhas) + "\n"


def secao_backend(api: dict | None) -> str:
    out = ["## 6. Backend", "", "### 6.1 Auditoria de API (api_audit.py)", "",
           "| Grupo | Item | Resultado | Detalhe |", "| --- | --- | --- | --- |"]
    if not api:
        out.append("| — | api.json ausente | — | rode scripts/qa/api_audit.py |")
    else:
        for i in api.get("itens", []):
            if i["grupo"] == "newman":
                continue
            st = {"PASSA": "PASSA", "FALHA": "FALHA"}.get(i["status"], "AVISO")
            out.append(f"| {i['grupo']} | {i['nome'].replace('|', '\\|')} | {st} | {(i.get('detalhe') or '—')[:140].replace('|', '\\|')} |")
    out += ["", "### 6.2 Newman", "", "| Coleção | Requests | Falhas | Classificação | Observação |", "| --- | --- | --- | --- | --- |"]
    for n in (api or {}).get("newman", []):
        obs = "; ".join(n.get("falhas_lista", [])[:2]) or n.get("erro", "—")
        out.append(f"| {n['colecao']} | {n.get('requests', '?')} | {n.get('falhas', '?')} | <contrato \\| fixture \\| legado> | {obs[:140].replace('|', '\\|')} |")
    for i in (api or {}).get("itens", []):
        if i["grupo"] == "newman" and i["status"] == "BLOQUEADO":
            out.append(f"| {i.get('detalhe', '—')} | — | — | legado | {i['nome'].replace('|', '\\|')} |")
    return "\n".join(out) + "\n"


def montar(run_dir: Path, run: str, existente: str | None) -> str:
    res = json.loads((run_dir / "resultados.json").read_text())
    api = json.loads((run_dir / "api.json").read_text()) if (run_dir / "api.json").exists() else None
    casos = res.get("casos", [])
    n_pass = sum(1 for c in casos if c["status"] == "PASSA")
    n_fail = sum(1 for c in casos if c["status"] == "FALHA")
    n_blq = sum(1 for c in casos if c["status"] == "BLOQUEADO")
    geradas = {"2": secao_ambiente(run_dir), "3": secao_casos(res), "4": secao_auditoria(res), "6": secao_backend(api)}
    manuais = {k: v.format(n=len(casos), n_pass=n_pass, n_fail=n_fail, n_blq=n_blq) for k, v in MANUAIS.items()}
    if existente:
        # substitui só as seções geradas, preservando as manuais já escritas
        texto = existente
        for num, corpo in geradas.items():
            padrao = re.compile(rf"## {num}\. .*?(?=\n## \d+\. |\Z)", re.S)
            texto = padrao.sub(lambda _m, corpo=corpo: corpo.rstrip("\n") + "\n", texto, count=1) if padrao.search(texto) else texto + "\n" + corpo
        return texto
    cab = CABECALHO.format(data=date.today().isoformat(), run=run, modo=res.get("modo", "—"), base=res.get("base", "—"),
                           telas=", ".join(res.get("telas", [])))
    ordem = ["2", "3", "4", "5", "6", "7", "8", "9"]
    return cab + "\n" + "\n".join((geradas.get(k) or manuais[k]).rstrip("\n") + "\n" for k in ordem)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True)
    p.add_argument("--repo", default=str(REPO))
    p.add_argument("--saida", default=None)
    a = p.parse_args(argv)
    run_dir = Path(a.repo) / ".qa" / "runs" / a.run
    if not (run_dir / "resultados.json").exists():
        print(f"resultados.json ausente em {run_dir}", file=sys.stderr)
        return 2
    saida = Path(a.saida) if a.saida else Path(a.repo) / "docs" / "qa" / "reports" / f"{date.today().isoformat()}-{a.run}" / "relatorio.md"
    saida.parent.mkdir(parents=True, exist_ok=True)
    existente = saida.read_text() if saida.exists() else None
    saida.write_text(montar(run_dir, a.run, existente))
    print(f"relatório: {saida} ({'seções 2/3/4/6 atualizadas' if existente else 'criado'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
