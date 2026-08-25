"""Contrato transversal do **guia por etapa** (wave 2).

Cada tela do Studio precisa dizer, sem o usuário adivinhar: o que a aula manda fazer nesta
etapa, quais entradas ainda faltam, quais validações passam ou falham e qual é a próxima
ação. Esse texto não é estado novo: ele é **calculado lendo os artefatos do projeto**
(ADR-003 — a fonte de verdade é o sistema de arquivos sob `projects/<id>/`).

Cada plugin pode exportar `studio/etapas/<id>/guide.py` com:

```python
def guide(pid: str) -> dict:
    g = Guide(META).text("O que a aula manda fazer…", ["checklist da aula"])
    g.input("refs_selected", "≥ 1 referência escolhida", exists(pid, "refs/brainstorming"),
            fix="Volte à etapa 1 e salve a seleção", step="refs")
    g.output("base_final", "base/base_final.png", exists(pid, "base/base_final.png"))
    g.check("upscale_2x", "Upscale 2x (aula 009)", "todo")
    return g.build()
```

Regras irrevogáveis do hook (o núcleo confia nelas):

- **É puro.** Só lê arquivos do projeto. Nunca cria nem regrava artefato, nunca chama CLI,
  ffprobe ou rede. Duas leituras "de status" do codebase têm efeito colateral de escrita
  (`edit.get_timeline`, `animate.load_plan`) — o guia **não** pode usá-las.
- **É barato.** É chamado 11 vezes por request no agregado `GET /api/projects/{pid}/guide`.
- **Não decide gate.** `validations` com `warn`/`fail` viram itens de atenção; só `inputs`
  com `fail` bloqueiam a etapa.

Etapas sem `guide.py` (ou cujo hook explode) recebem `generic_guide(META)`, com
`status: "unknown"` — nunca um 500.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..refs.service import project_dir

#: Estados possíveis de uma etapa. `unknown` = etapa sem hook de guia (ou hook com erro).
STATUS = ("todo", "blocked", "in_progress", "done", "unknown")
#: Estados possíveis de uma validação — nenhum deles bloqueia a etapa.
CHECK_STATUS = ("ok", "warn", "fail", "todo")

_AUTO = object()   # sentinela de `build(next_step=...)`: derivar do catálogo de etapas


# ---------- leitura pura de artefatos ----------
def _path(pid: str, rel: str) -> Path:
    """Caminho absoluto de `rel` dentro do projeto, sem deixar escapar da pasta dele."""
    root = project_dir(pid)
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ValueError(f"caminho fora do projeto: {rel}")
    return p


def exists(pid: str, rel: str) -> bool:
    """O artefato `rel` (arquivo ou pasta) existe no projeto?"""
    return _path(pid, rel).exists()


def read_json(pid: str, rel: str, default=None):
    """Lê um JSON do projeto; devolve `default` se não existir ou estiver corrompido."""
    p = _path(pid, rel)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def count_files(pid: str, rel: str, exts: set[str] | tuple[str, ...] | None = None) -> int:
    """Quantos arquivos há na pasta `rel` (não recursivo), opcionalmente filtrando extensões."""
    p = _path(pid, rel)
    if not p.is_dir():
        return 0
    wanted = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts} if exts else None
    return sum(1 for f in p.iterdir() if f.is_file() and (wanted is None or f.suffix.lower() in wanted))


def next_step_id(step_id: str) -> str | None:
    """Etapa seguinte na ordem do curso (`steps.SOON`); `None` se for a última."""
    from ..steps import SOON
    ids = [s["id"] for s in SOON]
    if step_id not in ids:
        return None
    i = ids.index(step_id)
    return ids[i + 1] if i + 1 < len(ids) else None


def _step_label(step_id: str | None) -> str:
    from ..steps import SOON
    for s in SOON:
        if s["id"] == step_id:
            return f"etapa {s['n']} ({s['title']})"
    return "a próxima etapa"


# ---------- builder ----------
class Guide:
    """Acumula entradas, saídas e validações de uma etapa e deriva status/progresso.

    Uso encadeado: `Guide(META).text(...).input(...).output(...).check(...).build()`.
    """

    def __init__(self, meta: dict):
        self.meta = dict(meta)
        self._what = ""
        self._checklist: list[str] = []
        self.inputs: list[dict] = []
        self.outputs: list[dict] = []
        self.validations: list[dict] = []

    # --- textos da aula ---
    def text(self, what: str, checklist: list[str] | None = None) -> Guide:
        """`what`: o que fazer nesta etapa (3–6 frases, pt-BR, fiel à aula).
        `checklist`: as regras de qualidade que o instrutor repete, em bullets."""
        self._what = what.strip()
        self._checklist = list(checklist or [])
        return self

    # --- itens ---
    def input(self, id: str, label: str, ok: bool, detail: str | None = None,
              fix: str | None = None, step: str | None = None) -> Guide:
        """Pré-requisito vindo de outra etapa. `ok=False` **bloqueia** a etapa.
        `step` é o id da etapa que produz o artefato (vira link "ir para lá" na UI)."""
        self.inputs.append(_item(id, label, "ok" if ok else "fail", detail, fix, step=step))
        return self

    def output(self, id: str, label: str, ok: bool, detail: str | None = None) -> Guide:
        """Artefato que esta etapa precisa produzir. O progresso é a fração de saídas `ok`."""
        self.outputs.append(_item(id, label, "ok" if ok else "todo", detail))
        return self

    def check(self, id: str, label: str, status: str, detail: str | None = None,
              fix: str | None = None) -> Guide:
        """Validação de qualidade (`ok|warn|fail|todo`). Nunca bloqueia — é item de atenção."""
        if status not in CHECK_STATUS:
            raise ValueError(f"status de validação inválido: {status}")
        self.validations.append(_item(id, label, status, detail, fix))
        return self

    # --- resultado ---
    def build(self, next_step=_AUTO, next_action: str | None = None) -> dict:
        """Fecha o guia: deriva `status`, `progress`, `missing` e a próxima ação."""
        sid = self.meta.get("id", "")
        status = self._status()
        done_out = [o for o in self.outputs if o["status"] == "ok"]
        progress = round(len(done_out) / len(self.outputs), 2) if self.outputs else 0.0
        step_next = next_step_id(sid) if next_step is _AUTO else next_step
        missing = [i["label"] for i in self.inputs if i["status"] != "ok"]
        missing += [o["label"] for o in self.outputs if o["status"] != "ok"]
        return {
            "id": sid, "n": self.meta.get("n"), "title": self.meta.get("title", ""),
            "aula": self.meta.get("aula", ""),
            "status": status, "progress": progress,
            "what": self._what, "checklist": self._checklist,
            "inputs": self.inputs, "outputs": self.outputs, "validations": self.validations,
            "missing": missing,
            "next_action": next_action or self._next_action(status, step_next),
            "next_step": step_next,
        }

    def _status(self) -> str:
        if any(i["status"] == "fail" for i in self.inputs):
            return "blocked"
        if not any(o["status"] == "ok" for o in self.outputs):
            return "todo"
        if all(o["status"] == "ok" for o in self.outputs):
            return "done"
        return "in_progress"

    def _next_action(self, status: str, step_next: str | None) -> str:
        if status == "blocked":
            first = next(i for i in self.inputs if i["status"] == "fail")
            return f"Antes de continuar: {first['label']}." + (f" {first['fix']}" if first.get("fix") else "")
        if status == "done":
            if step_next:
                return f"Etapa concluída — siga para a {_step_label(step_next)}."
            return "Etapa concluída — é a última etapa do curso."
        pending = next((o for o in self.outputs if o["status"] != "ok"), None)
        if pending:
            return f"Produza o próximo artefato: {pending['label']}."
        return "Siga o que está descrito em \"O que fazer\" nesta etapa."


def _item(id: str, label: str, status: str, detail: str | None = None,
          fix: str | None = None, step: str | None = None) -> dict:
    item = {"id": id, "label": label, "status": status}
    if detail:
        item["detail"] = detail
    if fix:
        item["fix"] = fix
    if step:
        item["step"] = step
    return item


def generic_guide(meta: dict, detail: str | None = None) -> dict:
    """Guia de fallback para etapa sem `guide.py` (ou cujo hook levantou exceção).

    `status: "unknown"` é o sinal para a UI: a etapa existe e funciona, mas ainda não sabe
    dizer o que falta. `detail` carrega o erro do hook, quando houver.
    """
    sid = meta.get("id", "")
    g = {
        "id": sid, "n": meta.get("n"), "title": meta.get("title", ""), "aula": meta.get("aula", ""),
        "status": "unknown", "progress": 0.0,
        "what": meta.get("desc", ""), "checklist": [],
        "inputs": [], "outputs": [], "validations": [], "missing": [],
        "next_action": "Abra a etapa e siga o que a tela pede — esta etapa ainda não tem guia detalhado.",
        "next_step": next_step_id(sid),
    }
    if detail:
        g["detail"] = detail
    return g
