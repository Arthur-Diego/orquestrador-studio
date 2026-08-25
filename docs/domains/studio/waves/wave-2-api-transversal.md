# Wave 2 — API transversal disponível para as frentes

Implementada pelo preparo (`ADH-OS-20260825-06`) **antes** das 7 frentes, para que nenhuma delas
edite arquivo único. Frentes devem **usar** estes contratos, nunca copiá-los nem alterá-los.

> **Regra de propriedade (HLD studio v1.2 · ADR-010):** `studio/app.py`, `studio/steps.py`,
> `studio/config.py`, `studio/higgsfield.py`, `studio/etapas/__init__.py` e `studio/web/*` são do
> preparo/shell. Frente de etapa mexe só em `studio/etapas/<id>/`, `studio/<id>/service.py`,
> `docs/domains/<etapa>/` e `tests/test_<etapa>_*`. Precisou de algo no núcleo? Peça — não edite.

---

## 1. O guia da sua etapa — `studio/etapas/<id>/guide.py`

Crie o arquivo com **uma** função `guide(pid) -> dict`. `discover()` a encontra sozinho (chave
`guide`, opcional); nada a registrar em lugar nenhum.

### Regras do hook (o núcleo confia nelas)

1. **É puro.** Só lê arquivos do projeto. Nunca cria nem regrava artefato, nunca chama CLI,
   `ffprobe` ou rede. Cuidado: `edit.get_timeline()` e `animate.load_plan()` **gravam ao ler** —
   use `edit.load_timeline()` e leia `animate/takes.json` direto.
2. **É barato.** É chamado 11 vezes por request no agregado `GET /api/projects/{pid}/guide`.
3. **Não decide gate.** Só `inputs` com `fail` bloqueiam; `validations` são atenção.
4. **Fala a língua da aula (ADR-004).** `what` e `checklist` vêm da aula da sua etapa — não
   invente regra que o instrutor não ensina; extensão aprovada aparece marcada `[extensão]`.
5. **Não pode explodir a tela.** Se explodir, o núcleo devolve o guia genérico (`status:
   "unknown"` + `detail` do erro) em vez de 500 — mas isso é bug seu, não um caminho aceitável.

### Exemplo completo (etapa fictícia `sample`, aula 042)

```python
"""Guia da etapa N (aula 042) — leitura pura dos artefatos do projeto."""
from ...common.guide import Guide, count_files, exists, read_json
from . import META


def guide(pid: str) -> dict:
    g = Guide(META).text(
        "O que a aula manda fazer aqui, em 3 a 6 frases, em pt-BR, sem inventar passo que a "
        "aula não ensina. Diga o artefato que sai daqui e para que ele serve na etapa seguinte.",
        ["Regra de qualidade que o instrutor repete",
         "Outra regra da aula (o checklist é da aula, não seu)"],
    )

    # Entradas: o que precisa vir de outra etapa. `ok=False` BLOQUEIA a etapa.
    g.input("base_final", "base/base_final.png (etapa 3)", exists(pid, "base/base_final.png"),
            fix="Volte à etapa 3 e escolha a imagem base", step="base")

    # Saídas: o que ESTA etapa produz. O progresso é a fração de saídas ok.
    plano = read_json(pid, "sample/plano.json", default={}) or {}
    n_frames = count_files(pid, "sample/frames", {".png", ".jpg"})
    g.output("plano", "sample/plano.json", bool(plano.get("cenas")),
             detail=f"{len(plano.get('cenas', []))} cenas")
    g.output("frames", "sample/frames/*.png", n_frames > 0, detail=f"{n_frames} frames")

    # Validações: qualidade. NUNCA bloqueiam — viram itens de "atenção".
    g.check("prompt_en", "Prompts em inglês (aula 007)", "ok" if plano.get("lang") == "en" else "warn",
            detail="a aula manda escrever o prompt em inglês")
    g.check("upscale", "Upscale aplicado", "todo" if not n_frames else "ok")

    return g.build()          # next_step = etapa seguinte no catálogo; passe next_step=... para mudar
```

### API de `studio/common/guide.py`

```python
Guide(meta)                                             # meta = o META do seu plugin
  .text(what: str, checklist: list[str] | None = None)
  .input(id, label, ok: bool, detail=None, fix=None, step=None)    # ok=False → status "fail" → BLOQUEIA
  .output(id, label, ok: bool, detail=None)                        # ok=False → status "todo"
  .check(id, label, status: "ok"|"warn"|"fail"|"todo", detail=None, fix=None)
  .build(next_step=<catálogo>, next_action=None) -> dict           # todos encadeáveis

exists(pid, rel) -> bool                                # arquivo ou pasta
read_json(pid, rel, default=None)                       # JSON corrompido → default (nunca levanta)
count_files(pid, rel, exts=None) -> int                 # não recursivo; exts {".png"} ou ("png",)
next_step_id(step_id) -> str | None                     # ordem do curso (steps.SOON)
generic_guide(meta, detail=None) -> dict                # fallback status "unknown"
```

`pid` inválido/inexistente levanta `KeyError` (o núcleo traduz em 404). `rel` que escape da pasta
do projeto levanta `ValueError`.

### Derivação automática (não reimplemente)

| Situação | `status` |
| --- | --- |
| alguma entrada `fail` | `blocked` |
| nenhuma saída `ok` (inclusive sem saídas) | `todo` |
| todas as saídas `ok` | `done` |
| resto | `in_progress` |

`progress` = saídas ok / saídas (0.0 sem saídas). `missing` = labels de entradas e saídas que não
estão `ok`. `next_action` sai de uma frase derivada (pendência bloqueante → próximo artefato →
"siga para a etapa seguinte"); passe `next_action=` só quando a aula pedir uma frase específica.

### Formato devolvido

```json
{"id": "base", "n": 3, "title": "Imagem base", "aula": "009",
 "status": "todo|blocked|in_progress|done|unknown", "progress": 0.0,
 "what": "…", "checklist": ["…"],
 "inputs":  [{"id": "…", "label": "…", "status": "ok|fail", "detail": "…", "fix": "…", "step": "refs"}],
 "outputs": [{"id": "…", "label": "…", "status": "ok|todo", "detail": "…"}],
 "validations": [{"id": "…", "label": "…", "status": "ok|warn|fail|todo", "detail": "…", "fix": "…"}],
 "missing": ["…"], "next_action": "…", "next_step": "storyboard"}
```

`detail` e `fix` só aparecem quando você passa (nunca vêm vazios).

---

## 2. Rotas novas do núcleo

```
GET   /api/projects/{pid}                 project.json + {progress, current}
PATCH /api/projects/{pid}                 {name?, product?, vibe?, aspect_ratio?, brand?}
                                          aspect_ratio ∈ 16:9 (default) | 9:16 | 1:1  → 422 fora disso
                                          campo ausente não é apagado; grava project.json atômico
GET   /api/projects/{pid}/guide           {steps: [Guide × 11], done, total, progress, current}
GET   /api/projects/{pid}/guide/{step}    Guide  (404 se a etapa não existe)
GET   /api/higgsfield/status[?refresh=1]  cache de 60 s no backend
```

`vibe` é **opcional na criação** (aula 009: a vibe é encontrada na etapa 2). A frente `refs+mood`
grava a vibe depois via `PATCH /api/projects/{pid}` — não crie campo novo em `project.json`.

`current` é o id da primeira etapa que não está `done` (`null` se todas estiverem).

---

## 3. `Studio.ui` — `studio/web/ui.js` + `ui.css`

Carregados pelo `index.html` **antes** do `app.js` e dos plugins; servidos em `/static/ui.js` e
`/static/ui.css`. Substituem o código duplicado hoje em 7 views (`esc`, chip do CLI, drag&drop,
upload multipart, `confirm()` de custo, polling de 3 s).

```js
Studio.ui.esc(s) -> string                       // escape de HTML: TODO dado da API passa por aqui
Studio.ui.chip(text, kind="mode") -> string      // kind: "ok" | "warn" | "mode"
await Studio.ui.hfChip(el) -> status             // preenche o chip do CLI e devolve {installed, logged_in, plan, credits}
Studio.ui.drop(el, onFiles) -> input             // drag&drop + "escolha arquivos" (classe .over no arraste)
await Studio.ui.upload(url, files, field="files") -> json   // multipart; lança Error com o detail da API
await Studio.ui.confirmCost(costFn, label) -> bool          // custo estimado + confirm(); custo indisponível não trava
Studio.ui.poll(fn, ms=3000) -> {stop()}          // para em stop(), em fn() === false, ou em 3 erros seguidos
Studio.ui.guide(el, guideObj)                    // renderiza o painel padrão
await Studio.ui.renderGuide(stepId, el?) -> guideObj|null   // busca a rota e renderiza no #guide
```

### Convenção de tela (obrigatória nesta wave)

```html
<header class="stephead">
  <span class="eyebrow">Etapa N · aula X</span>   <!-- string fixada por teste: não mexer -->
  <h2>…</h2>
  <p class="lede">…</p>
</header>
<section id="guide" class="guide"></section>       <!-- o painel do guia mora aqui -->
```

```js
Studio.register("sample", (ctx) => {
  const { $, api, toast } = ctx;
  let job = null;                                    // handle do poll

  async function gerar() {
    const ok = await Studio.ui.confirmCost(
      () => api(`/api/projects/${ctx.pid()}/sample/cost`, { method: "POST", body: "{}" }),
      "Gerar 4 imagens via CLI");
    if (!ok) return;
    await api(`/api/projects/${ctx.pid()}/sample/generate`, { method: "POST", body: "{}" });
    job = Studio.ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/sample/job`);
      $("#sampleLog").textContent = j.state === "running" ? `${j.done}/${j.total}` : j.state;
      if (j.state !== "running") { carregar(); ctx.guide(); return false; }   // false encerra o poll
    }, 3000);
  }

  return {
    init() {
      Studio.ui.drop($("#sampleDrop"), async (files) => {
        try {
          const r = await Studio.ui.upload(`/api/projects/${ctx.pid()}/sample/import/upload`, files);
          toast(`${r.added} importadas`); carregar(); ctx.guide();            // guia sempre que muda artefato
        } catch (e) { toast(e.message); }
      });
      $("#btnGerar").onclick = gerar;
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      Studio.ui.hfChip($("#sampleHf")).then(s => { $("#btnGerar").disabled = !s.logged_in; });
      await carregar();
      Studio.ui.renderGuide("sample");        // ou ctx.guide(), que renderiza o da etapa em exibição
    },
    destroy() { if (job) job.stop(); },       // OBRIGATÓRIO: sem isso o poll sobrevive à troca de tela
  };
});
```

- **`destroy()` é obrigatório** em toda instância de plugin: `app.js` chama antes de trocar de
  tela. Pare ali todo `poll()` e todo `setTimeout` seu. É critério cross-feature da wave.
- Chame `ctx.guide()` (ou `Studio.ui.renderGuide("<id>")`) em `onProject()` **e depois de cada
  ação que muda artefato** — importar, gerar, selecionar, renderizar.
- `Studio.go("<step>")` navega para outra etapa; os links "ir para a etapa" do painel de guia já
  usam isso a partir do `step` que você passa em `.input(..., step="base")`.
- Nunca interpole dado da API em HTML sem `Studio.ui.esc()`.
- `ui.css` usa só as variáveis de `style.css` (claro/escuro saem de graça). Não edite `ui.css`
  nem `style.css` — a frente shell redesenha.

---

## 4. `PROJECT_LAYOUT` e `higgsfield.status()`

- Todo projeto novo já nasce com `base/`, `storyboard/`, `storyboard/ideas/`, `shots/`,
  `animate/`, `publish/`, `prospect/`, `mood/vibe/` (além das antigas). **Consequência para
  testes:** não asserte mais "a pasta X não existe" para provar que um GET não escreve — asserte
  que a pasta está **vazia**.
- `hf.status()` é cacheado por 60 s no módulo. Em teste, `hf.reset_status_cache()` zera; quem
  monkeypatcha `hf.status` diretamente não é afetado.

## 5. Testes

Continuam sem rede e sem navegador (ADR-008): asserts HTTP e de string. O guia é fácil de testar
por HTTP — crie o projeto, escreva os artefatos pelo serviço da etapa e verifique
`GET /api/projects/{pid}/guide/<id>`:

```python
def test_guide_da_etapa(client, studio_env):
    pid = client.post("/api/projects", json={"name": "G"}).json()["id"]
    g = client.get(f"/api/projects/{pid}/guide/sample").json()
    assert g["status"] == "blocked" and "base/base_final.png (etapa 3)" in g["missing"]
    assert g["next_step"] == "…" and g["what"]
```

Exemplos completos em `tests/test_guide.py` (builder, derivação, fallback e rotas).
