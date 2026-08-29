"""Auditoria de backend do QA E2E (skill qa-studio) — fora do CI (ADR-008).

    . .venv/bin/activate
    python scripts/qa/api_audit.py --run <run-id> [--sem-newman] [--dominios base music ...]

Contra o servidor isolado da rodada (`stack-up.sh` + `seed.sh`):
1. **Varredura do OpenAPI** (`/openapi.json`): todo GET responde < 500 e em < 5 s; toda rota com
   `{pid}` devolve 404 (nunca 500) para pid inexistente; todo POST/PUT/PATCH com corpo inválido
   devolve 4xx (nunca 500). Mutações rodam num projeto/board DESCARTÁVEL clonado do seed — o
   `pid_cheio` nunca é tocado.
2. **Contratos conhecidos**: 409 em projeto duplicado, 422 em `aspect_ratio` inválido, 404 em reset
   de etapa desconhecida, catálogo de etapas coerente com o guia, endpoints `/job` com `state`.
3. **Modo offline**: nenhum binário real foi chamado (só há chamadas no `fakes.log`).
4. **Log do servidor**: `Traceback`/`ERROR` em `server.log` viram apontamento.
5. **Newman**: cada coleção em `docs/domains/*/postman/` roda com `baseUrl`/`base_url`, `pid`
   (clone descartável), `pidVazio` e `pidInexistente` injetados; sumário por coleção.

Saída: `.qa/runs/<run-id>/api.json` + sumário no stdout. Exit 1 se houver FALHA.
Nunca chama: `/api/pinterest/login` (abre navegador), `open-folder` (abre o explorer do SO).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.qa import harness as H  # noqa: E402

NUNCA = ("/api/pinterest/login", "/open-folder")
LATENCIA_MAX_S = 5.0


class Auditoria:
    def __init__(self, ctx: H.Ctx) -> None:
        self.ctx = ctx
        self.c = httpx.Client(base_url=ctx.base, timeout=120)
        self.itens: list[dict] = []
        self.pid_tmp: str | None = None
        self.mbid_tmp: str | None = None

    # ---- registro ----
    def item(self, grupo: str, nome: str, ok: bool, detalhe: str = "", **extra) -> bool:
        self.itens.append({"grupo": grupo, "nome": nome, "status": H.PASSA if ok else H.FALHA, "detalhe": detalhe, **extra})
        print(("✓ " if ok else "✗ ") + f"[{grupo}] {nome}" + (f"  — {detalhe[:160]}" if not ok else ""))
        return ok

    def aviso(self, grupo: str, nome: str, detalhe: str = "") -> None:
        self.itens.append({"grupo": grupo, "nome": nome, "status": H.BLOQUEADO, "detalhe": detalhe})
        print(f"⊘ [{grupo}] {nome}  — {detalhe[:160]}")

    # ---- recursos descartáveis ----
    def clonar_projeto(self, nome: str) -> str:
        """Clona o pid_cheio num pid novo (dir + `id` do project.json)."""
        from studio.refs.service import slugify  # só string, sem tocar em config
        pid = f"{datetime.now():%Y-%m}-{slugify(nome)}"
        dest = self.ctx.projeto(pid)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.ctx.projeto(self.ctx.pid_cheio), dest)
        meta = json.loads((dest / "project.json").read_text())
        meta.update(id=pid, name=nome)
        (dest / "project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        return pid

    def preparar(self) -> None:
        self.pid_tmp = self.clonar_projeto("QA API Audit")
        r = self.c.post("/api/moodboards", json={"name": "QA API Board", "note": "descartável"})
        self.mbid_tmp = r.json()["id"] if r.status_code in (200, 201) else "qa-api-board"

    # ---- 1) varredura do OpenAPI ----
    def valores_de_path(self) -> dict[str, str]:
        pid = self.pid_tmp or self.ctx.pid_cheio
        ready = [s["id"] for s in self.ctx.steps if s["status"] == "ready"]
        v = {"pid": pid, "mbid": self.mbid_tmp or self.ctx.mbid, "step": ready[0] if ready else "refs",
             "step_id": ready[0] if ready else "refs", "asset": "view.html", "scene": "cena01", "shot": "shot01",
             "take": "1", "lid": "lead-x", "post_id": "post-x", "cid": "cand-x", "action": "situation", "path": "x"}
        # descobre ids reais quando existirem (cena, lead, post) para os GETs não caírem só em 404
        try:
            sc = self.c.get(f"/api/projects/{pid}/storyboard/scenes").json()
            cenas = sc.get("scenes", sc) if isinstance(sc, dict) else sc
            if isinstance(cenas, list) and cenas and isinstance(cenas[0], dict) and cenas[0].get("id"):
                v["scene"] = cenas[0]["id"]
        except Exception:  # noqa: BLE001
            pass
        try:
            leads = self.c.get(f"/api/projects/{pid}/prospect/leads").json()
            if isinstance(leads, list) and leads and leads[0].get("id"):
                v["lid"] = leads[0]["id"]
        except Exception:  # noqa: BLE001
            pass
        try:
            log = self.c.get(f"/api/projects/{pid}/publish/log").json()
            posts = log.get("posts", log) if isinstance(log, dict) else log
            if isinstance(posts, list) and posts and posts[0].get("id"):
                v["post_id"] = posts[0]["id"]
        except Exception:  # noqa: BLE001
            pass
        return v

    def varrer_openapi(self) -> None:
        spec = self.c.get("/openapi.json").json()
        valores = self.valores_de_path()
        rotas = []
        for path, ops in spec["paths"].items():
            if any(n in path for n in NUNCA):
                continue
            for metodo, op in ops.items():
                if metodo.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    continue
                rotas.append((metodo.upper(), path, op))
        self.item("openapi", f"{len(rotas)} operações descobertas", len(rotas) > 50, f"{len(rotas)} (esperado > 50)")

        def preencher(path: str, subst: dict[str, str]) -> str:
            return re.sub(r"\{(\w+)\}", lambda m: subst.get(m.group(1), "x"), path)

        # 1a) GETs reais < 500 e rápidos
        lentos, quinhentos = [], []
        for metodo, path, _ in rotas:
            if metodo != "GET" or "{path}" in path:
                continue
            url = preencher(path, valores)
            t0 = time.time()
            try:
                r = self.c.get(url)
            except httpx.HTTPError as e:
                quinhentos.append(f"GET {url}: {e}")
                continue
            dt = time.time() - t0
            if r.status_code >= 500:
                quinhentos.append(f"GET {url} → {r.status_code} {r.text[:120]}")
            if dt > LATENCIA_MAX_S:
                lentos.append(f"GET {url}: {dt:.1f}s")
        self.item("openapi", "nenhum GET responde 5xx", not quinhentos, "; ".join(quinhentos[:8]), lista=quinhentos)
        self.item("openapi", f"nenhum GET acima de {LATENCIA_MAX_S:.0f}s", not lentos, "; ".join(lentos[:8]), lista=lentos)

        # 1b) pid inexistente → 404 (nunca 500), em todas as rotas com {pid}
        ruins = []
        for metodo, path, op in rotas:
            if "{pid}" not in path:
                continue
            url = preencher(path, {**valores, "pid": "projeto-que-nao-existe"})
            # FastAPI valida query obrigatória ANTES do handler: 422 é aceitável nesses GETs
            query_obrig = any(p.get("in") == "query" and p.get("required") for p in op.get("parameters", []))
            try:
                r = self.c.request(metodo, url, json={} if metodo in ("POST", "PUT", "PATCH") else None)
            except httpx.HTTPError as e:
                ruins.append(f"{metodo} {url}: {e}")
                continue
            aceitos = (404, 422) if query_obrig else (404,)
            if r.status_code >= 500 or (metodo == "GET" and r.status_code not in aceitos):
                ruins.append(f"{metodo} {url} → {r.status_code}")
        self.item("contratos", "pid inexistente devolve 404 (GET) e nunca 5xx", not ruins, "; ".join(ruins[:8]), lista=ruins)

        # 1c) corpo inválido em POST/PUT/PATCH → 4xx, nunca 5xx (no projeto descartável)
        ruins = []
        for metodo, path, op in rotas:
            if metodo not in ("POST", "PUT", "PATCH"):
                continue
            url = preencher(path, valores)
            corpos: list[tuple[str, dict]] = [("json {}", {"json": {}}), ("json lixo", {"json": {"__qa_lixo__": [1, 2]}})]
            if "multipart/form-data" in json.dumps(op.get("requestBody", {})):
                corpos = [("multipart vazio", {"data": {}})]
            for rotulo, kw in corpos:
                try:
                    r = self.c.request(metodo, url, **kw)
                except httpx.HTTPError as e:
                    ruins.append(f"{metodo} {url} ({rotulo}): {e}")
                    continue
                if r.status_code >= 500:
                    ruins.append(f"{metodo} {url} ({rotulo}) → {r.status_code} {r.text[:100]}")
        self.item("contratos", "corpo inválido em POST/PUT/PATCH nunca devolve 5xx", not ruins, "; ".join(ruins[:8]), lista=ruins)

        # 1d) endpoints /job têm `state`
        ruins = []
        for metodo, path, _ in rotas:
            if metodo == "GET" and path.endswith("/job"):
                r = self.c.get(preencher(path, valores))
                if r.status_code == 200 and "state" not in r.json():
                    ruins.append(f"{path} sem 'state': {r.text[:80]}")
        self.item("contratos", "todo GET …/job devolve {state}", not ruins, "; ".join(ruins))

    # ---- 2) contratos conhecidos ----
    def contratos(self) -> None:
        steps = self.ctx.steps
        self.item("catalogo", "/api/steps tem 10 etapas com n=1..10", [s["n"] for s in steps] == list(range(1, 11)),
                  str([s["n"] for s in steps]))
        guide = self.c.get(f"/api/projects/{self.ctx.pid_cheio}/guide").json()
        self.item("catalogo", "guia.total == etapas ready", guide.get("total") == sum(1 for s in steps if s["status"] == "ready"),
                  f"total={guide.get('total')} ready={sum(1 for s in steps if s['status'] == 'ready')}")
        r = self.c.post("/api/projects", json={"name": "QA API Audit", "product": ""})
        self.item("contratos", "POST /api/projects duplicado → 409", r.status_code == 409, f"→ {r.status_code}")
        r = self.c.patch(f"/api/projects/{self.pid_tmp}", json={"aspect_ratio": "4:3"})
        self.item("contratos", "PATCH aspect_ratio inválido → 422", r.status_code == 422, f"→ {r.status_code}")
        r = self.c.post(f"/api/projects/{self.pid_tmp}/steps/etapa-x/reset")
        self.item("contratos", "reset de etapa desconhecida → 404", r.status_code == 404, f"→ {r.status_code}")
        r = self.c.get(f"/api/projects/{self.pid_tmp}/guide/etapa-x")
        self.item("contratos", "guia de etapa desconhecida → 404", r.status_code == 404, f"→ {r.status_code}")
        r = self.c.get("/api/higgsfield/status")
        self.item("contratos", "/api/higgsfield/status tem installed/logged_in",
                  {"installed", "logged_in"} <= set(r.json()), r.text[:120])
        r = self.c.post("/api/projects", json={"name": "moodboards"})
        self.item("contratos", "pid reservado ('moodboards') é recusado", r.status_code in (409, 422), f"→ {r.status_code}")
        meta = json.loads((self.ctx.projeto(self.ctx.pid_cheio) / "project.json").read_text())
        self.item("disco", "project.json do seed cheio continua íntegro após a auditoria",
                  meta.get("id") == self.ctx.pid_cheio, str(meta)[:120])

    # ---- 3) offline ----
    def offline(self) -> None:
        if self.ctx.modo != "offline":
            self.aviso("offline", "modo real — verificação de fakes não se aplica")
            return
        log = self.ctx.fakes_log()
        self.item("offline", "fakes foram chamados (higgsfield/claude passam pelos fakes)", "higgsfield" in log,
                  "fakes.log sem chamadas de higgsfield — o servidor pode estar usando o binário real")

    # ---- 4) log do servidor ----
    def server_log(self) -> None:
        log_path = self.ctx.run_dir / "server.log"
        txt = log_path.read_text(errors="replace") if log_path.exists() else ""
        tracebacks = txt.count("Traceback (most recent call last)")
        erros = [ln for ln in txt.splitlines() if " 500 " in ln or "ERROR" in ln]
        self.item("server.log", "sem Traceback no log do servidor", tracebacks == 0, f"{tracebacks} traceback(s) em {log_path}")
        self.item("server.log", "sem respostas 500 / linhas ERROR", not erros, "; ".join(erros[:5]), lista=erros[:20])

    # ---- 5) newman ----
    def newman(self, dominios: list[str] | None) -> list[dict]:
        out: list[dict] = []
        if not shutil.which("newman"):
            self.aviso("newman", "newman ausente no PATH — coleções não executadas")
            return out
        pid_newman = self.clonar_projeto("QA Newman")
        vivos = {s["id"] for s in self.ctx.steps if s["status"] == "ready"} | {"studio", "moodboards", "creditos", "higgsfield"}
        for col in sorted(REPO.glob("docs/domains/*/postman/*.postman_collection.json")):
            dominio = col.parents[1].name
            if dominios and dominio not in dominios:
                continue
            if dominio not in vivos:
                self.aviso("newman", f"{dominio}: domínio legado sem plugin — coleção não executada",
                           str(col.relative_to(REPO)))
                continue
            envs = list(col.parent.glob("*.postman_environment.json"))
            rel = self.ctx.run_dir / f"newman-{dominio}.json"
            cmd = ["newman", "run", str(col), "--reporters", "cli,json", "--reporter-json-export", str(rel),
                   "--suppress-exit-code", "--timeout-request", "120000",
                   "--env-var", f"baseUrl={self.ctx.base}", "--env-var", f"base_url={self.ctx.base}",
                   "--env-var", f"pid={pid_newman}", "--env-var", f"pidVazio={self.ctx.pid_vazio}",
                   "--env-var", "pidInexistente=projeto-que-nao-existe"]
            if envs:
                cmd += ["-e", str(envs[0])]
            t0 = time.time()
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=col.parent)
            (self.ctx.run_dir / f"newman-{dominio}.log").write_text(p.stdout + "\n" + p.stderr)
            stats = {}
            try:
                run = json.loads(rel.read_text())["run"]
                st = run["stats"]
                stats = {"requests": st["requests"]["total"], "asserts": st["assertions"]["total"],
                         "falhas": st["assertions"]["failed"], "erros": len(run.get("failures", [])),
                         "falhas_lista": [f"{f.get('source', {}).get('name', '?')}: {f.get('error', {}).get('message', '')[:100]}"
                                          for f in run.get("failures", [])][:15]}
            except Exception as e:  # noqa: BLE001
                stats = {"erro": f"sem relatório json: {e}"}
            reg = {"dominio": dominio, "colecao": str(col.relative_to(REPO)), "segundos": round(time.time() - t0, 1), **stats}
            out.append(reg)
            ok = stats.get("erros", 1) == 0 and stats.get("falhas", 1) == 0
            self.item("newman", f"{dominio}: {stats.get('requests', '?')} requests, {stats.get('falhas', '?')} falhas", ok,
                      "; ".join(stats.get("falhas_lista", [])[:4]) or stats.get("erro", ""))
        return out

    def fechar(self) -> None:
        self.c.close()


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True)
    p.add_argument("--repo", default=str(REPO))
    p.add_argument("--sem-newman", action="store_true")
    p.add_argument("--dominios", nargs="*", default=None, help="só estas coleções Postman")
    a = p.parse_args(argv)
    run_dir = Path(a.repo) / ".qa" / "runs" / a.run
    ctx = H.Ctx.da_rodada(run_dir)
    aud = Auditoria(ctx)
    ctx.steps = aud.c.get("/api/steps").json()
    aud.preparar()
    aud.varrer_openapi()
    aud.contratos()
    aud.offline()
    newman = [] if a.sem_newman else aud.newman(a.dominios)
    aud.server_log()
    aud.fechar()
    res = {"run": a.run, "base": ctx.base, "modo": ctx.modo, "quando": datetime.now(timezone.utc).isoformat(),
           "itens": aud.itens, "newman": newman}
    (run_dir / "api.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    falhas = [i for i in aud.itens if i["status"] == H.FALHA]
    print(f"\nauditoria de API: {len(aud.itens) - len(falhas)} ok, {len(falhas)} falha(s) → {run_dir / 'api.json'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
