"""Tools de AÇÃO do MCP (ADR-037), Onda B. Conduzem a criação pelas rotas da API.

Dois padrões estruturantes:
- **Gate de custo embutido (ADR-016/038).** Toda geração paga passa por `_paid`: estima o custo,
  pede a confirmação ao usuário (`ui.confirm_cost`) e só então gera. O agente não tem como pular —
  não há tool paga que gere sem passar por aqui. No terminal (sem UI), exige `confirm=true`.
- **Escolha visual do usuário (ADR-038).** As tools `*_pick` buscam as candidatas, mostram a grade
  (`ui.choose_images`) e aplicam a seleção — em uma tool só, sem despejar dezenas de ids no modelo.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from . import ui
from .client import StudioApiError, StudioClient

log = logging.getLogger(__name__)

#: Chaves de lista aceitas quando a rota de candidatas devolve um **dict** em vez de uma lista.
#: Os shapes são diferentes por domínio, por design (base publica `{candidates, final}`, storyboard
#: publica `{ideas}`, refs/mood/personagem publicam lista pura) — o consumidor é que é tolerante,
#: as rotas não mudam (ADR-037: o MCP é cliente da API, a correção mora no cliente).
CAND_KEYS = ("candidates", "ideas", "items")

#: Cadeia de fallback do rótulo da grade, aplicada depois da chave preferida da etapa. Sem ela,
#: base, refs e storyboard exibiriam legenda vazia (só mood tem `batch`).
LABEL_KEYS = ("batch", "kind", "term", "label", "name")
LABEL_MAX = 60


# ---------- helpers ----------
def _candidate_rows(payload: Any) -> list[dict]:
    """Normaliza o shape da resposta de candidatas para uma lista de linhas `dict`.

    Lista devolve as linhas que são `dict`; dict devolve a primeira lista entre `CAND_KEYS`;
    qualquer outra coisa devolve `[]`. NUNCA levanta: shape inesperado vira "sem candidatas",
    que a tool traduz em texto acionável.
    """
    rows: Any = payload
    if isinstance(payload, dict):
        rows = next((v for k in CAND_KEYS if isinstance(v := payload.get(k), list)), None)
    if not isinstance(rows, list):
        return []
    return [c for c in rows if isinstance(c, dict)]


def _media_url(prefix: str, step: str, thumb: str) -> str:
    """URL servível da thumb. `thumb` já absoluto passa direto; já prefixado com `<step>/` (base e
    storyboard, relativos à raiz do projeto) só recebe o prefixo; relativo recebe o caminho inteiro.
    """
    if thumb.startswith("/") or thumb.startswith("http"):
        return thumb
    if thumb.startswith(f"{step}/"):
        return f"{prefix}/{thumb}"
    return f"{prefix}/{step}/candidates/{thumb}"


def _truncar(texto: str) -> str:
    """Corte único da legenda da grade, com reticência. Compartilhado pelas duas montagens de
    payload (`_label`, das etapas, e `_mb_label`, da biblioteca): a constante é a mesma, o
    comportamento tem de ser o mesmo."""
    return texto if len(texto) <= LABEL_MAX else texto[:LABEL_MAX - 1] + "…"


def _label(c: dict, label_key: str) -> str:
    """Legenda da grade: a chave preferida da etapa, a cadeia de fallback e, por último, o prompt.
    Truncada, porque a legenda fica sob a miniatura e o prompt de storyboard é uma frase inteira."""
    for k in (label_key, *LABEL_KEYS, "prompt"):
        v = c.get(k)
        if isinstance(v, str) and v.strip():
            return _truncar(v.strip())
    return ""


def _images_for(pid: str, step: str, cands: Any, label_key: str = "batch") -> list[dict]:
    """Payload de `ui.choose_images` a partir de qualquer shape publicado pelas rotas de candidatas."""
    out = []
    for c in _candidate_rows(cands):
        thumb = c.get("thumb")
        cid = c.get("id")
        if not thumb or not isinstance(thumb, str) or not cid:
            continue
        out.append({"id": cid, "thumb": _media_url(f"/files/{pid}", step, thumb),
                    "label": _label(c, label_key)})
    return out


def _next_step(client: StudioClient, pid: str) -> str | None:
    """Próxima etapa **segundo o backend** (`current` do guia). Nunca calculada aqui (ADR-010 a);
    qualquer falha de leitura degrada para `None` — o dado é enriquecimento, não fluxo."""
    try:
        guide = client.get(f"/api/projects/{pid}/guide")
    except StudioApiError:
        return None
    current = guide.get("current") if isinstance(guide, dict) else None
    return current if isinstance(current, str) else None


def _result_json(selected: list[str], next_step: str | None) -> str:
    """Sufixo maquinalmente legível do retorno das `*_pick` (contrato consumido pelo chat).

    Sempre a ÚLTIMA linha, sempre começando por `{"selected":`, emitido só quando a seleção foi
    de fato gravada — a ausência do sufixo significa "nada foi selecionado".
    """
    return json.dumps({"selected": list(selected), "next_step": next_step},
                      ensure_ascii=False, separators=(", ", ": "))


def _credits(cost: dict) -> Any:
    for k in ("total", "credits", "cost"):
        v = cost.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


#: Campos do `CostPreview` (`studio/common/pricing.py`) que o dock precisa para montar as linhas.
_CAMPOS_BREAKDOWN = ("action", "model", "label", "variant", "kind", "unit_credits", "count",
                     "total", "source", "balance", "note")


def _breakdown(cost: dict, *, model: str, credits: Any) -> dict:
    """Extrai do retorno da rota `cost` o detalhamento que o widget do chat renderiza.

    Pura. `[extensão]` wave 11 (ADR-016): antes o gate do chat recebia só um escalar, e o cartão
    degradava para duas linhas enquanto as telas mostravam a planilha inteira. Aqui o
    `CostPreview` atravessa inteiro.

    `credits` continua no dict de fora como o escalar de sempre; `balance_after` é derivado só
    quando saldo e total existem — sem os dois, o dock omite a linha, como o `CostSheet` faz.
    """
    b = {k: cost[k] for k in _CAMPOS_BREAKDOWN if k in cost}
    b.setdefault("model", model)
    if b.get("unit_credits") is None and isinstance(credits, (int, float)):
        b["unit_credits"] = credits
    if b.get("total") is None and isinstance(credits, (int, float)):
        b["total"] = credits
    saldo = (b.get("balance") or {}).get("credits")
    total = b.get("total")
    if isinstance(saldo, (int, float)) and isinstance(total, (int, float)):
        b["balance_after"] = round(saldo - total, 2)
    return b


def _linhas_markdown(b: dict, credits: Any) -> str:
    """O mesmo detalhamento em texto, para o caminho TERMINAL — onde o único canal é texto."""
    linhas = []
    if b.get("model"):
        rotulo = b.get("label") or b["model"]
        linhas.append(f"- Modelo: {rotulo}" + (f" · {b['variant']}" if b.get("variant") else ""))
    unit = b.get("unit_credits")
    if isinstance(unit, (int, float)):
        fonte = {"cli": " (CLI)", "measured": " (medido)"}.get(b.get("source") or "", "")
        linhas.append(f"- Custo por geração: {unit} créditos{fonte}")
    n = b.get("count") or 1
    if isinstance(n, int) and n > 1:
        linhas.append(f"- Quantidade: {n}×")
    linhas.append(f"- Total estimado: {credits} créditos" if credits is not None
                  else "- Total estimado: indisponível")
    saldo = (b.get("balance") or {}).get("credits")
    if isinstance(saldo, (int, float)):
        linhas.append(f"- Saldo atual: {saldo} créditos")
        if "balance_after" in b:
            linhas.append(f"- Saldo depois: {b['balance_after']} créditos")
        if isinstance(b.get("total"), (int, float)) and saldo < b["total"]:
            linhas.append("- ⚠ Saldo menor que o total estimado.")
    return "\n".join(linhas)


def _paid(client: StudioClient, *, step: str, cost_path: str, cost_body: dict, gen_path: str,
          gen_body: dict, action: str, model: str, confirm: bool, follow: str | None = None,
          model_from_cost: bool = False) -> str:
    """Gate de custo único das gerações pagas (ADR-016/038).

    `follow` nomeia a tool de espera quando o job NÃO é de etapa (jobs de URL própria, como os da
    biblioteca de mood boards). Sem ele, o texto continua apontando `job_wait` — o default preserva
    byte a byte o retorno de todos os chamadores existentes.

    `model_from_cost` deixa a RESPOSTA do cost nomear o modelo. Serve para as rotas em que quem
    escolhe o modelo é o servidor quando o usuário não pede um (multishot): sem isso o sheet de
    gasto diria "modelo padrão", e num gate de custo o modelo cobrado é o dado que mais importa.
    Também é aditivo: nenhum chamador existente liga a flag.
    """
    try:
        cost = client.post(cost_path, cost_body) or {}
    except StudioApiError as e:
        return str(e)
    if model_from_cost:
        real = cost.get("model")
        if isinstance(real, str) and real.strip():
            model = real.strip()
    credits = _credits(cost)
    cred_txt = credits if credits is not None else "não estimável"
    b = _breakdown(cost, model=model, credits=credits)
    cid = ui.chat_id()
    log.info("mcp: gate de custo action=%s model=%s total=%s source=%s chat=%s",
             action, model, b.get("total"), b.get("source"), cid)
    if cid:
        ans = ui.confirm_cost(client, action, cred_txt, model, breakdown=b)
        if not ans.get("answered") or not ans.get("confirmed"):
            log.info("mcp: gate de custo resultado=%s action=%s", "cancelado", action)
            return f"Geração cancelada pelo usuário (custo estimado: {cred_txt} créditos)."
        # ADR-038 §3: nenhuma tool paga executa sem um `confirm_token` emitido por `confirm_cost`.
        if ui.CONFIRM_TOKEN_REQUIRED and not ui.consume_confirm_token(
                ans.get("_confirm_token"), action=action, model=model):
            log.info("mcp: gate de custo resultado=%s action=%s", "sem_token", action)
            return ("Confirmação de gasto inválida ou expirada. Peça a confirmação de novo "
                    "chamando esta tool outra vez.")
        log.info("mcp: gate de custo resultado=%s action=%s", "confirmado", action)
    elif not confirm:
        log.info("mcp: gate de custo resultado=%s action=%s", "terminal", action)
        detalhe = _linhas_markdown(b, credits)
        return (f"Custo estimado: {cred_txt} créditos ({model}).\n{detalhe}\n"
                "Para gerar, chame esta tool de novo com confirm=true.")
    try:
        client.post(gen_path, gen_body)
    except StudioApiError as e:
        return str(e)
    # Duas intenções no mesmo retorno: o waiter certo (F12 — jobs de URL própria não são de etapa)
    # e o eco do que foi aprovado (F10 — o usuário fecha o turno vendo o que autorizou gastar).
    aprovado = f" Custo aprovado: {cred_txt} créditos."
    if follow:
        return f"Geração iniciada ({model}). Acompanhe com `{follow}`.{aprovado}"
    return (f"Geração iniciada ({model}). Acompanhe com `job_wait` (etapa {step})."
            f"{aprovado}")


def _pick(client: StudioClient, *, pid: str, step: str, cands_path: str, select_path: str,
          title: str, minimum: int, maximum: int | None, select_body,
          cands_params: dict | None = None, label_key: str = "batch",
          empty_text: str | None = None, ok_text: Callable[[list[str]], str] | None = None,
          no_ui_text: str | None = None, no_answer_text: str | None = None) -> str:
    """Fluxo único das `*_pick` de etapa: busca candidatas, mostra a grade, aplica a seleção.

    Os textos são parametrizáveis para que cada etapa preserve a frase que já usa hoje; o sufixo
    JSON só sai no caminho em que o `select` gravou.
    """
    try:
        payload = client.get(cands_path, cands_params)
    except StudioApiError as e:
        return str(e)
    imgs = _images_for(pid, step, payload, label_key)
    if not imgs:
        return empty_text or f"Nenhuma candidata na etapa {step} ainda — gere ou importe antes de escolher."
    ans = ui.choose_images(client, title, imgs, minimum=minimum, maximum=maximum)
    if ans.get("no_ui"):
        return no_ui_text.format(ids=", ".join(i["id"] for i in imgs)) if no_ui_text else (
            "Sem interface para escolher aqui. Candidatas disponíveis: "
            + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return no_answer_text or "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return no_answer_text or "O usuário não selecionou nenhuma imagem."
    try:
        client.post(select_path, select_body(ids))
    except StudioApiError as e:
        return str(e)
    texto = ok_text(ids) if ok_text else f"{len(ids)} imagem(ns) selecionada(s) e salva(s) na etapa {step}."
    return f"{texto}\n{_result_json(ids, _next_step(client, pid))}"


# ---------- 1 · Referências ----------
def refs_suggest_terms(client: StudioClient, product: str = "", vibe: str = "", brand: str = "",
                       pid: str = "") -> str:
    terms = client.get("/api/suggest-terms", {"product": product, "vibe": vibe, "brand": brand, "pid": pid}) or []
    return "Termos sugeridos: " + ", ".join(terms) if terms else "Nenhum termo sugerido (informe o produto)."


def refs_search(client: StudioClient, pid: str, terms: list[str], max_per_term: int = 30) -> str:
    if not terms:
        return "Passe ao menos um termo de busca."
    client.post(f"/api/projects/{pid}/refs/search", {"terms": terms, "max_per_term": max_per_term, "headless": True})
    return (f"Busca no Pinterest iniciada para {len(terms)} termo(s). Acompanhe com `job_wait` "
            "(etapa refs); depois use `refs_pick` para o usuário escolher.")


def refs_pick(client: StudioClient, pid: str) -> str:
    return _pick(client, pid=pid, step="refs", cands_path=f"/api/projects/{pid}/refs/candidates",
                 select_path=f"/api/projects/{pid}/refs/select",
                 title="Escolha as referências que você gosta", minimum=1, maximum=None,
                 select_body=lambda ids: {"ids": ids, "notes": {}}, label_key="term")


# ---------- 2 · Mood board ----------
def mood_prompt(client: StudioClient, pid: str, mode: str = "brief", instruction: str = "",
                purpose: str = "", tone: str = "", reference: str = "", model: str = "nano_banana_2") -> str:
    resp = client.post(f"/api/projects/{pid}/mood/prompts/generate",
                       {"mode": mode, "instruction": instruction, "purpose": purpose, "tone": tone,
                        "reference": reference, "model": model}) or {}
    prompt = resp.get("prompt") if isinstance(resp, dict) else None
    return f"Prompt de vibe gerado:\n{prompt}" if prompt else f"Prompt gerado: {resp}"


def mood_generate(client: StudioClient, pid: str, prompts: list[str], count: int = 2,
                  model: str = "nano_banana_2", aspect_ratio: str = "16:9", resolution: str = "2k",
                  confirm: bool = False) -> str:
    if not prompts:
        return "Passe ao menos um prompt de vibe (use `mood_prompt` para gerá-lo)."
    body = {"model": model, "prompts": prompts, "aspect_ratio": aspect_ratio, "resolution": resolution, "count": count}
    return _paid(client, step="mood", cost_path=f"/api/projects/{pid}/mood/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/mood/generate", gen_body=body,
                 action="Gerar grid de mood", model=model, confirm=confirm)


def mood_pick(client: StudioClient, pid: str, note: str = "") -> str:
    return _pick(client, pid=pid, step="mood", cands_path=f"/api/projects/{pid}/mood/candidates",
                 select_path=f"/api/projects/{pid}/mood/select",
                 title="Escolha as imagens do mood (mesma vibe)", minimum=1, maximum=8,
                 select_body=lambda ids: {"ids": ids, "note": note})


# ---------- 3 · Imagem base ----------
def base_prompt(client: StudioClient, pid: str, ref_id: str | None = None, mode: str = "images",
                instruction: str = "") -> str:
    prefix = _character_prefix(client, pid)
    if prefix:
        instruction = (f"Keep this exact character identity: {prefix}. " + instruction).strip()
    resp = client.post(f"/api/projects/{pid}/base/prompts/generate",
                       {"ref_id": ref_id, "mode": mode, "instruction": instruction}) or {}
    prompt = resp.get("prompt") if isinstance(resp, dict) else None
    return f"Prompt da base gerado:\n{prompt}" if prompt else f"Prompt gerado: {resp}"


def base_generate(client: StudioClient, pid: str, kind: str = "situation", prompt: str = "",
                  count: int | None = None, model: str | None = None, confirm: bool = False) -> str:
    body: dict = {"kind": kind, "prompt": prompt}
    if count is not None:
        body["count"] = count
    if model:
        body["model"] = model
    return _paid(client, step="base", cost_path=f"/api/projects/{pid}/base/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/base/generate", gen_body=body,
                 action="Gerar imagem base", model=model or "default", confirm=confirm)


def base_pick(client: StudioClient, pid: str, note: str = "") -> str:
    # a base final é UMA imagem; select da base recebe {id, note}. `GET /base/candidates` devolve
    # um DICT (`{candidates, final}`) e a `thumb` já vem prefixada com `base/` — os dois casos são
    # tratados pelos helpers compartilhados, e é por isso que esta tool não tem laço próprio.
    return _pick(client, pid=pid, step="base", cands_path=f"/api/projects/{pid}/base/candidates",
                 select_path=f"/api/projects/{pid}/base/select",
                 title="Escolha a imagem base final", minimum=1, maximum=1,
                 select_body=lambda ids: {"id": ids[0], "note": note}, label_key="kind",
                 empty_text="Nenhuma candidata de base ainda — gere com `base_generate` antes.",
                 ok_text=lambda ids: "Imagem base escolhida e salva.",
                 no_ui_text="Sem interface aqui. Candidatas: {ids}. Diga qual escolher.",
                 no_answer_text="O usuário não escolheu a base.")


# ---------- 3 · Imagem base · revisão das candidatas NOVAS `[extensão]` ----------
#: Ordem de avanço da cadeia da etapa 3, do passo mais cru ao mais acabado. Espelha `KINDS` do
#: serviço de propósito: o MCP é cliente HTTP da própria API e NUNCA importa `studio.base.*`
#: (ADR-037); o `kind` é contrato público, publicado em `GET /base/candidates`.
BASE_KINDS = ("situation", "clean", "label", "upscale")
BASE_KIND_LABEL = {"situation": "situação", "clean": "limpeza", "label": "rótulo",
                   "upscale": "upscale 2x"}
BASE_KIND_TITULO = {"situation": "Imagem de situação pronta", "clean": "Limpeza pronta",
                    "label": "Rótulo pronto", "upscale": "Upscale 2x pronto"}


def _base_rows(cands: Any, *, thumb_key: str, file_key: str) -> list[dict]:
    """Normaliza candidatas da etapa 3 para a linha única que a grade e os pares consomem.

    As duas fontes publicam shapes diferentes, por design: `new_candidates` traz `thumb_url`/
    `file_url` já absolutos (e `thumb_url` pode ser `None`), `GET /base/candidates` traz
    `thumb`/`file` relativos à raiz do projeto. A prefixação continua sendo de `_media_url`,
    chamado por `_images_for` e por `_base_media` — aqui só se escolhe a URL disponível.
    """
    out = []
    for c in _candidate_rows(cands):
        cid = c.get("id")
        thumb, arquivo = c.get(thumb_key), c.get(file_key)
        url = arquivo if isinstance(arquivo, str) and arquivo else thumb
        if not cid or not isinstance(url, str) or not url:
            continue
        kind = c.get("kind") if isinstance(c.get("kind"), str) else ""
        out.append({"id": cid, "kind": kind, "source_id": c.get("source_id"), "file": url,
                    "thumb": thumb if isinstance(thumb, str) and thumb else url,
                    "label": BASE_KIND_LABEL.get(kind, kind)})
    return out


def _base_pendentes(brutas: Any, rows: list[dict]) -> list[dict]:
    """Candidatas do `kind` mais avançado que ainda NÃO tem seleção — o que falta revisar na etapa.

    É o fallback de quando não houve job (`state:"idle"`): sem candidata nova, o que interessa ao
    usuário é o último passo da cadeia que ele ainda não decidiu.
    """
    selecionados = {c.get("kind") for c in _candidate_rows(brutas) if c.get("selected")}
    presentes = {r["kind"] for r in rows}
    alvo = next((k for k in reversed(BASE_KINDS) if k in presentes and k not in selecionados), None)
    return [r for r in rows if r["kind"] == alvo] if alvo else []


def _base_media(pid: str, rows: list[dict], origem: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """`(itens do ui.show, itens media do ask)`. O par antes/depois só existe quando a origem ainda
    está na etapa; sem `source_id` (ou com a origem apagada) só a imagem nova aparece (§6)."""
    prefixo = f"/files/{pid}"
    mostra: list[dict] = []
    media: list[dict] = []
    for r in rows:
        depois = {"url": _media_url(prefixo, "base", r["file"]),
                  "label": f"depois ({r['label']})" if r["label"] else "depois",
                  "kind": "image", "role": "after", "pair": r["id"]}
        src = origem.get(r.get("source_id") or "")
        if src is None or src["id"] == r["id"]:
            mostra.append({k: v for k, v in depois.items() if k not in ("role", "pair")})
            continue
        antes = {"url": _media_url(prefixo, "base", src["file"]),
                 "label": f"antes ({src['label']})" if src["label"] else "antes",
                 "kind": "image", "role": "before", "pair": r["id"]}
        mostra += [antes, depois]
        media += [antes, depois]
    return mostra, media


def _base_texto(avisos: list[str], texto: str) -> str:
    """Junta os avisos (job com erro, ids ignorados) ao texto, numa linha só — o sufixo JSON da
    seleção precisa continuar sendo a ÚLTIMA linha do retorno."""
    return " ".join([*avisos, texto])


def base_review(client: StudioClient, pid: str, ids: list[str] | None = None, note: str = "") -> str:
    """`[extensão]` Revisão das candidatas NOVAS da etapa 3 (upscale/limpeza/rótulo) pelo chat.

    Lê `new_candidates` do job, mostra o par antes→depois (`ui.show`) e abre a grade com
    `min=0`/`max=1` mais os botões de ação, para que "não trocar" seja resposta válida
    (ADR-038, decisão 6). `POST /base/select` só acontece com um `ask` respondido e um id vindo
    da resposta. Não gera nada: nunca passa por `_paid` nem por rota de custo (ADR-016).
    """
    try:
        job = client.get(f"/api/projects/{pid}/base/job")
    except StudioApiError as e:
        return str(e)
    if not isinstance(job, dict):
        job = {}
    if job.get("state") == "running":
        return (f"Ainda gerando ({job.get('done') or 0}/{job.get('total') or 0}). "
                "Espere com `job_wait` e chame `base_review` de novo.")
    avisos: list[str] = []
    if job.get("state") == "error":
        avisos.append(f"O job da etapa base falhou: {job.get('error') or 'erro desconhecido'}.")
    rows = _base_rows(job.get("new_candidates"), thumb_key="thumb_url", file_key="file_url")

    # `GET /base/candidates` é opcional (§5): só é buscado quando falta a origem do par, quando o
    # usuário passou ids ou quando não houve job (fallback).
    origem: dict[str, dict] = {}
    if not rows or ids or any(r.get("source_id") for r in rows):
        try:
            etapa = client.get(f"/api/projects/{pid}/base/candidates")
        except StudioApiError as e:
            if not rows:
                return str(e)   # sem job E sem candidatas: o erro é a única informação útil
            etapa = None
        todas = _base_rows(etapa, thumb_key="thumb", file_key="file")
        origem = {r["id"]: r for r in todas}
        if not rows:
            rows = todas if ids else _base_pendentes(etapa, todas)

    if ids:
        faltando: list[str] = []
        escolhidas: list[dict] = []
        for i in ids:
            alvo = next((r for r in rows if r["id"] == i), None) or origem.get(i)
            if alvo is None:
                faltando.append(i)
            elif all(e["id"] != alvo["id"] for e in escolhidas):
                escolhidas.append(alvo)
        if faltando:
            avisos.append("Ignorei ids que não existem na etapa 3: " + ", ".join(faltando) + ".")
        rows = escolhidas

    imgs = _images_for(pid, "base", rows, label_key="label")
    if not imgs:
        return _base_texto(avisos, "Nenhuma candidata nova na etapa 3. Gere com `base_generate` "
                                   "ou importe pela tela.")

    kind = next((k for k in reversed(BASE_KINDS) if any(r["kind"] == k for r in rows)), "")
    titulo = BASE_KIND_TITULO.get(kind, "Novas candidatas da etapa 3")
    mostra, media = _base_media(pid, rows, origem)
    acoes = [{"label": "Usar como imagem base", "value": {"selected": [r["id"]]}, "for": r["id"]}
             for r in rows]
    acoes.append({"label": "Manter a atual", "value": {"selected": [], "keep": True}})
    ui.show(client, mostra, titulo)
    ans = ui.choose_images(client, f"{titulo}. Qual imagem vira a base final?", imgs,
                           minimum=0, maximum=1, media=media, actions=acoes) or {}

    if ans.get("no_ui"):
        lista = ", ".join(f"{r['id']} ({_media_url(f'/files/{pid}', 'base', r['file'])})" for r in rows)
        return _base_texto(avisos, f"Sem interface para escolher aqui. Novas candidatas: {lista}. "
                                   "Diga qual usar como base.")
    if not ans.get("answered"):
        return _base_texto(avisos, "O usuário não escolheu (sem resposta). Você pode perguntar de novo.")
    escolha = ans.get("selected") or []
    if ans.get("keep") or not escolha:
        return _base_texto(avisos, "Mantive a imagem base atual.")

    cid = escolha[0]
    try:
        client.post(f"/api/projects/{pid}/base/select", {"id": cid, "note": note})
    except StudioApiError as e:
        return str(e)
    alvo = next((r for r in rows if r["id"] == cid), {})
    rot = alvo.get("label") or ""
    src = origem.get(alvo.get("source_id") or "")
    detalhe = f" ({rot}, origem `{src['id']}`)" if rot and src else (f" ({rot})" if rot else "")
    texto = f"Imagem base atualizada: `{cid}`{detalhe}.\nFinal gravada em `base/base_final.png`."
    return f"{_base_texto(avisos, texto)}\n{_result_json([cid], _next_step(client, pid))}"

# ---------- 4 · Storyboard (motor local grátis + escolha) ----------
def storyboard_local_generate(client: StudioClient, pid: str, prompt: str, count: int = 4,
                              model: str = "flux-schnell") -> str:
    if not prompt.strip():
        return "Escreva o prompt do keyframe (em inglês, aula 007)."
    prefix = _character_prefix(client, pid)
    if prefix:
        prompt = f"{prompt}. Character identity (keep identical): {prefix}"
    try:
        client.post(f"/api/projects/{pid}/storyboard/local/generate",
                    {"prompt": prompt, "count": count, "model": model})
    except StudioApiError as e:
        return str(e)  # 409 se o motor local (engine/ComfyUI) estiver offline
    return f"Keyframes locais (grátis) sendo gerados com {model}. Acompanhe com `job_wait` (etapa storyboard)."


def storyboard_pick(client: StudioClient, pid: str) -> str:
    # `GET /storyboard/candidates` devolve `{"ideas": [...]}` (chave `ideas`, não `candidates`) e a
    # `thumb` já vem prefixada com `storyboard/` — ambos tratados por `_candidate_rows`/`_media_url`.
    return _pick(client, pid=pid, step="storyboard", cands_path=f"/api/projects/{pid}/storyboard/candidates",
                 select_path=f"/api/projects/{pid}/storyboard/candidates/select",
                 title="Escolha os keyframes do storyboard", minimum=1, maximum=None,
                 select_body=lambda ids: {"ids": ids})


# `[extensão]` geração POR CENA (FDD storyboard-geracao-por-cena §5, contratos 6 e 7). Paridade
# tela × agente: as duas pontes que a tela ganhou (motor local grátis e CLI pago) e a escolha dos
# frames da cena. Como toda tool do MCP, são clientes HTTP da própria API — nada importa
# `studio.storyboard.*` (ADR-037).
SCENE_ENGINES = ("local", "cli")


def _scene_prompt(client: StudioClient, pid: str, scene: str) -> str:
    """1º prompt de ângulo da cena, para o modo `cli` sem prompt (leitura DEFENSIVA: falhou, vazio)."""
    try:
        resp = client.get(f"/api/projects/{pid}/storyboard/angles/scenes/{scene}/prompts") or {}
    except StudioApiError:
        return ""
    prompts = resp.get("prompts") if isinstance(resp, dict) else None
    first = (prompts or [{}])[0] if prompts else {}
    return (first.get("text") or "").strip() if isinstance(first, dict) else ""


def storyboard_scene_generate(client: StudioClient, pid: str, scene: str, engine: str = "local",
                              prompt: str = "", count: int = 4, model: str = "",
                              confirm: bool = False) -> str:
    """Gera a imagem/os ângulos de UMA cena. `engine="local"` é grátis; `"cli"` passa por `_paid`."""
    if engine not in SCENE_ENGINES:
        return f"engine inválido: {engine} (use local ou cli)."
    if engine == "local":
        body = (prompt or "").strip()
        if not body:
            return f"Escreva o prompt da cena {scene} (em inglês, aula 007)."
        prefix = _character_prefix(client, pid)
        if prefix:
            body = f"{body}. Character identity (keep identical): {prefix}"
        gen_model = model or "flux-schnell"
        try:
            client.post(f"/api/projects/{pid}/storyboard/local/generate",
                        {"prompt": body, "count": count, "model": gen_model, "scene": scene})
        except StudioApiError as e:
            return str(e)  # 409 motor offline · 404 cena desconhecida · 422 pedido inválido
        return (f"Imagem da cena {scene} sendo gerada no motor LOCAL (grátis) com {gen_model}. "
                "Acompanhe com `job_wait` (etapa storyboard).")
    texto = (prompt or "").strip() or _scene_prompt(client, pid, scene)
    if not texto:
        return f"Sem prompt para a cena {scene}: escreva um ou prepare a base para o builder de ângulos."
    gen_model = model or "nano_banana_2"
    body = {"model": gen_model, "prompts": [texto], "count": count, "resolution": "2k"}
    return _paid(client, step=f"storyboard/{scene}",
                 cost_path=f"/api/projects/{pid}/storyboard/angles/scenes/{scene}/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/storyboard/angles/scenes/{scene}/generate", gen_body=body,
                 action=f"Gerar ângulos da cena {scene}", model=gen_model, confirm=confirm)


def storyboard_scene_pick(client: StudioClient, pid: str, scene: str) -> str:
    """Mostra os candidatos DA CENA para o usuário escolher e ordenar (ADR-038, humano no laço).

    Normaliza a resposta localmente (`{scene, base, candidates}`) em vez de usar o `_pick` genérico,
    que trata a resposta como lista — e monta a thumb com o caminho JÁ relativo à raiz do projeto
    que `angles.list_candidates` devolve (`storyboard/cenaNN/candidates/thumbs/<sha12>.jpg`).
    """
    try:
        resp = client.get(f"/api/projects/{pid}/storyboard/angles/scenes/{scene}/candidates") or {}
    except StudioApiError as e:
        return str(e)
    cands = resp.get("candidates") if isinstance(resp, dict) else resp
    imgs = [{"id": c["id"], "thumb": f"/files/{pid}/{c['thumb']}",
             "label": c.get("prompt") or c.get("name") or ""}
            for c in (cands or []) if c.get("thumb")]
    if not imgs:
        return (f"Nenhum candidato na cena {scene} ainda: gere (local ou CLI) ou importe antes "
                "de escolher.")
    ans = ui.choose_images(client, f"Escolha e ORDENE os frames da cena {scene}", imgs,
                           minimum=1, maximum=None)
    if ans.get("no_ui"):
        return ("Sem interface para escolher aqui. Candidatas disponíveis: "
                + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return "O usuário não selecionou nenhuma imagem."
    try:
        saved = client.post(f"/api/projects/{pid}/storyboard/angles/scenes/{scene}/select",
                            {"shots": [{"id": i} for i in ids]}) or {}
    except StudioApiError as e:
        return str(e)
    shots = saved.get("shots") if isinstance(saved, dict) else None
    nomes = [str(s.get("file") or "").rsplit("/", 1)[-1] for s in (shots or [])] or \
        [f"shot{i:02d}_final.png" for i in range(1, len(ids) + 1)]
    return (f"{len(ids)} shot(s) escolhido(s) e ordenado(s) na cena {scene} "
            f"({', '.join(n for n in nomes if n)}).")


def storyboard_scenes(client: StudioClient, pid: str) -> str:
    resp = client.get(f"/api/projects/{pid}/storyboard/scenes") or {}
    scenes = resp.get("scenes") if isinstance(resp, dict) else resp
    if not scenes:
        return "Nenhuma cena definida ainda no storyboard."
    linhas = [f"{i + 1}. {s.get('text', s) if isinstance(s, dict) else s}" for i, s in enumerate(scenes)]
    return "Cenas do storyboard:\n" + "\n".join(linhas)


# ---------- 5 · Animação ----------
def animate_shots(client: StudioClient, pid: str) -> str:
    resp = client.get(f"/api/projects/{pid}/animate/shots") or {}
    shots = resp.get("shots") if isinstance(resp, dict) else resp
    n = len(shots) if isinstance(shots, list) else "?"
    return f"Shots para animar: {n}. Use `animate_generate` para gerar um take (pago) e `job_wait`."


def animate_generate(client: StudioClient, pid: str, scene: str, shot: str, model: str = "kling3_0",
                     count: int = 2, prompt: str = "", confirm: bool = False) -> str:
    cost_body = {"scene": scene, "shot": shot, "model": model, "count": count}
    gen_body = {**cost_body, "prompt": prompt or None}
    return _paid(client, step="animate", cost_path=f"/api/projects/{pid}/animate/cost", cost_body=cost_body,
                 gen_path=f"/api/projects/{pid}/animate/generate", gen_body=gen_body,
                 action=f"Animar take (cena {scene}, shot {shot})", model=model, confirm=confirm)


# ---------- 6 · Trilha ----------
def music_generate(client: StudioClient, pid: str, prompt: str = "", duration: int = 30,
                   confirm: bool = False) -> str:
    body = {"prompt": prompt, "duration": duration}
    return _paid(client, step="music", cost_path=f"/api/projects/{pid}/music/generate/cost", cost_body=body,
                 gen_path=f"/api/projects/{pid}/music/generate", gen_body=body,
                 action="Gerar trilha", model="sonilo_music", confirm=confirm)


# ---------- 7 · Montagem (ffmpeg, grátis) ----------
def edit_render(client: StudioClient, pid: str) -> str:
    try:
        client.post(f"/api/projects/{pid}/edit/render", {})
    except StudioApiError as e:
        return str(e)
    return "Montagem (render por ffmpeg, grátis) iniciada. Acompanhe com `job_wait` (etapa edit)."


# ---------- 8 · Export ----------
def export_render(client: StudioClient, pid: str, formats: list[str] | None = None) -> str:
    body = {"formats": formats or ["16x9", "9x16", "1x1"]}
    try:
        client.post(f"/api/projects/{pid}/export/render", body)
    except StudioApiError as e:
        return str(e)
    return "Export (formatos + thumb, grátis) iniciado. Acompanhe com `job_wait` (etapa export)."


def export_qa(client: StudioClient, pid: str) -> str:
    resp = client.post(f"/api/projects/{pid}/export/qa", {}) or {}
    return f"QA técnico do export: {resp}"


# ---------- 9 · Publicar ----------
def portfolio(client: StudioClient) -> str:
    resp = client.get("/api/portfolio") or {}
    return f"Portfólio: {resp}"


# ---------- Biblioteca de mood boards `[extensão]` (ADR-013) ----------
# Bloco contíguo no fim do arquivo (antes do bloco de personagem) por decisão da wave 11: seis
# frentes tocam este arquivo ao mesmo tempo, e acrescentar sempre no fim é o que mantém o rebase
# barato. Tudo aqui é cliente HTTP da própria API em loopback (ADR-037): nenhuma função deste bloco
# importa `studio.moodboards`, `studio.mood` ou qualquer serviço de etapa.

#: Origens de importação que o chat alcança. `upload` é recusado em texto: o assistente nunca
#: manipula os bytes das imagens do usuário (ADR-040) — isso é da tela.
MB_IMPORT_SOURCES = ("downloads", "history")


def _mb_label(c: dict) -> str:
    """Legenda da grade do board: a origem da candidata (`downloads`, `upload`, `multishot`…),
    caindo para o nome do arquivo e, por último, o prompt (truncado, como nas etapas)."""
    for k in ("source", "name", "prompt"):
        v = c.get(k)
        if isinstance(v, str) and v.strip():
            return _truncar(v.strip())
    return ""


def _mb_images(mbid: str, cands: Any) -> list[dict]:
    """Payload de `ui.choose_images` para as candidatas de um MOOD BOARD da biblioteca.

    O shape deste domínio é OUTRO, e confundi-lo com o das etapas é o risco 1 desta frente (recon
    §4): `GET /api/moodboards/{mbid}/candidates` devolve **lista pura**, a `thumb` é relativa ao
    diretório `candidates/` do board (`thumbs/<sha12>.jpg`, porque a biblioteca ingere com
    `step=""`) e o mount estático é `/mbfiles`, não `/files`. Por isso NÃO se usa `_images_for`
    nem `_media_url` aqui: eles montam `/files/{pid}/{step}/candidates/...`, e prefixar um thumb
    que já vem prefixado é exatamente o defeito de `base_pick` que a F04 corrigiu — na biblioteca
    sairia pior, porque não existe `pid` nem `step` para prefixar.
    """
    out = []
    for c in _candidate_rows(cands):
        cid, thumb = c.get("id"), c.get("thumb")
        if not cid or not isinstance(thumb, str) or not thumb:
            continue
        out.append({"id": cid, "thumb": f"/mbfiles/{mbid}/candidates/{thumb}", "label": _mb_label(c)})
    return out


def _wait_job(client: StudioClient, job_path: str, *, timeout: int = 600,
              _sleep: Callable[[float], None] = time.sleep) -> tuple[str, dict]:
    """Espera GENÉRICA sobre a URL de um job arbitrário, no molde de `character_wait`.

    Os jobs da biblioteca (mood-run, multishot) têm URL própria, diferente da URL de job das
    etapas — por isso `job_wait` NÃO serve para eles. Polling de 2 s, sem retry de escrita.

    Devolve `(estado, job)`:
    - `("idle", {})` — nunca rodou (`state == "idle"` sem nunca ter visto `running`);
    - `("error", job)` — terminou com `job["error"]` preenchido;
    - `("done", job)` — terminou; o job final vai inteiro para o chamador formatar o texto;
    - `("timeout", {})` — estourou `timeout` sem terminar;
    - `("http", {"error": <texto>})` — a rota falhou (404, Studio fora do ar…).

    A espera consome um ORÇAMENTO (`restante`), não um relógio de parede: com `_sleep` injetado
    (os testes), o caminho de timeout fecha em `timeout/2` iterações instantâneas em vez de virar
    busy-wait de segundos reais. Em produção, `_sleep` é `time.sleep` e o orçamento é o mesmo
    tempo de antes.
    """
    restante = float(max(1, timeout))
    viu_running = False
    while restante > 0:
        try:
            job = client.get(job_path) or {}
        except StudioApiError as e:
            return "http", {"error": str(e)}
        if job.get("state") == "running":
            viu_running = True
            _sleep(2.0)
            restante -= 2.0
            continue
        if job.get("state") == "idle" and not viu_running:
            return "idle", {}
        if job.get("error"):
            return "error", job
        return "done", job
    return "timeout", {}


def _sugerir_tela(client: StudioClient, alvo: str, texto: str) -> str:
    """Manda o usuário concluir na tela — ÚNICO ponto de troca com a frente F08 (chat-navigate).

    Hoje a navegação para áreas GLOBAIS não existe: o `navigate` do shell monta `#/<pid>/<alvo>` e
    a guarda de rota devolve o usuário para `overview` (recon §1.3/§4). Então o helper degrada para
    a instrução textual por `ui.notify` e devolve a mesma frase. Quando a F08 integrar, o corpo
    passa a chamar `ui_navigate(alvo)` (ex.: `moodboards/<mbid>`) e NENHUM chamador muda.
    """
    ui.notify(client, texto)
    return texto


def moodboard_list(client: StudioClient) -> str:
    try:
        boards = client.get("/api/moodboards") or []
    except StudioApiError as e:
        return str(e)
    linhas = [f"- **{b.get('name') or b.get('id')}** (`{b.get('id')}`), "
              f"{b.get('count', 0)} imagem(ns) curada(s)"
              + (f", vibe: {b['vibe']}" if b.get("vibe") else "")
              for b in boards if isinstance(b, dict)]
    if not linhas:
        return "Nenhum mood board na biblioteca ainda. Crie um com `moodboard_create`."
    return ("Mood boards da biblioteca (global, `[extensão]`):\n" + "\n".join(linhas)
            + "\nUse `moodboard_get` para ver um board ou `moodboard_create` para começar outro.")


def moodboard_get(client: StudioClient, mbid: str) -> str:
    try:
        b = client.get(f"/api/moodboards/{mbid}") or {}
    except StudioApiError as e:
        return str(e)
    cands = [c for c in (b.get("candidates") or []) if isinstance(c, dict)]
    cores = (b.get("palette") or {}).get("colors") or []
    linhas = [f"Mood board **{b.get('name') or mbid}** (`{b.get('id') or mbid}`)",
              f"- Vibe: {b.get('vibe') or '(a definir)'} · nota: {b.get('note') or '(sem nota)'}",
              f"- {len(cands)} candidata(s) importada(s), {b.get('count', 0)} curada(s) "
              "(teto de 8, uma vibe por board, ADR-007)"]
    if cores:
        linhas.append("- Paleta: " + ", ".join(cores))
    if b.get("prompt"):
        linhas.append(f"- Prompt de vibe: {b['prompt']}")
    ids = [c["id"] for c in cands if c.get("id")]
    if ids:
        linhas.append("- Candidatas para curar: " + ", ".join(ids) + " (use `moodboard_pick`)")
    return "\n".join(linhas)


def moodboard_create(client: StudioClient, name: str, note: str = "") -> str:
    try:
        b = client.post("/api/moodboards", {"name": name, "note": note}) or {}
    except StudioApiError as e:
        # A sugestão é do 409 (o slug já existe); o 422 é nome vazio, e mandar listar boards ali
        # seria conselho errado (FDD §6).
        if e.status == 409:
            return f"{e}\nVeja os boards que já existem com `moodboard_list`."
        return str(e)
    return (f"Mood board **{b.get('name') or name}** criado (id `{b.get('id', '')}`). "
            "Importe imagens com `moodboard_import`.")


def moodboard_patch(client: StudioClient, mbid: str, name: str = "", note: str = "",
                    vibe: str = "") -> str:
    """Edita os metadados do board: rótulo, nota e — o que importa — a VIBE em palavras.

    Sem esta tool o chat não fecha o fluxo A: `moodboard_create` nasce com `vibe: ""` e é
    `PATCH` quem grava a vibe, que `mood_pull` copia para a campanha (contrato 15). O `mbid` é
    ESTÁVEL: `name` muda só o rótulo, nunca o id (ADR-019, "salvar por nome" é abrir a pasta).

    Só os campos preenchidos vão no corpo: `None` no `BoardPatch` significa "não mexe", e mandar
    string vazia apagaria o que já está lá.
    """
    corpo = {k: v.strip() for k, v in (("name", name), ("note", note), ("vibe", vibe)) if v.strip()}
    if not corpo:
        return ("Nada a editar: passe pelo menos um de name, note ou vibe. A vibe em palavras é o "
                "que `mood_pull` leva para a campanha.")
    try:
        b = client.patch(f"/api/moodboards/{mbid}", corpo) or {}
    except StudioApiError as e:
        return str(e)
    mudou = ", ".join(f"{k}: {b.get(k, corpo[k])!r}" for k in corpo)
    return (f"Mood board `{b.get('id') or mbid}` atualizado ({mudou}). O id do board não muda "
            "quando o nome muda.")


def moodboard_import(client: StudioClient, mbid: str, source: str = "downloads",
                     since_minutes: int = 120) -> str:
    """Importa candidatas para o board a partir da pasta Downloads ou do histórico da Higgsfield.

    `source="upload"` é recusado ANTES de qualquer chamada de rota: o agente não manipula bytes
    (ADR-040), então o upload continua exclusivo da tela do board.
    """
    if source == "upload":
        # A recusa passa pelo `_sugerir_tela` porque o caminho que sobra para o usuário é a TELA:
        # é o ponto em que a costura com a F08 (chat-navigate) importa de verdade. Hoje o helper
        # só emite o aviso e devolve o texto — `ui.notify` sem `chat_id` não chama rota nenhuma,
        # então a recusa continua sendo "nenhuma requisição HTTP".
        return _sugerir_tela(
            client, f"moodboards/{mbid}",
            "Enviar arquivos pelo chat não é possível: eu nunca manipulo os bytes das suas "
            "imagens (ADR-040).\nSalve as imagens na pasta Downloads e use "
            'source="downloads", ou abra Biblioteca › Mood boards na barra lateral, escolha o '
            f"board `{mbid}` e faça o upload pela tela.")
    if source not in MB_IMPORT_SOURCES:
        return (f'Origem de importação desconhecida: "{source}". Use source="downloads" (pasta '
                'Downloads) ou source="history" (histórico da Higgsfield).')
    if source == "history":
        try:
            r = client.post(f"/api/moodboards/{mbid}/import/history", {}) or {}
        except StudioApiError as e:
            return str(e)
        return (f"{r.get('added', 0)} imagem(ns) importada(s) do histórico da Higgsfield "
                f"({r.get('jobs', 0)} job(s) lido(s)).\nAgora cure o board com `moodboard_pick`.")
    try:
        r = client.post(f"/api/moodboards/{mbid}/import/downloads",
                        {"folder": None, "since_minutes": since_minutes}) or {}
    except StudioApiError as e:
        # 404 aqui é a PASTA que não existe (o `FileNotFoundError` traduzido no router), não o
        # board: repassar o texto seco mandaria o agente procurar um board que está lá (FDD §6).
        if e.status == 404 and "pasta" in str(e).lower():
            return (f"{e}\nSalve as imagens na pasta Downloads (ou importe do histórico com "
                    'source="history") e chame `moodboard_import` de novo.')
        return str(e)
    return (f"{r.get('added', 0)} imagem(ns) importada(s) da pasta Downloads "
            f"({r.get('scanned', 0)} arquivo(s) varrido(s) em {r.get('folder', '?')}).\n"
            "Agora cure o board com `moodboard_pick`.")


def moodboard_pick(client: StudioClient, mbid: str, note: str = "") -> str:
    """Mostra as candidatas do board e persiste SÓ o que o usuário escolheu na grade (ADR-038)."""
    try:
        cands = client.get(f"/api/moodboards/{mbid}/candidates")
    except StudioApiError as e:
        return str(e)
    imgs = _mb_images(mbid, cands)
    if not imgs:
        return (f"O board `{mbid}` ainda não tem candidatas para curar. Importe imagens antes com "
                "`moodboard_import`.")
    ans = ui.choose_images(client, f"Escolha as imagens do board {mbid} (uma vibe só, até 8)",
                           imgs, minimum=1, maximum=8)
    if ans.get("no_ui"):
        return (f"Sem interface para escolher aqui. Candidatas do board `{mbid}`: "
                + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return "O usuário não selecionou nenhuma imagem do board."
    try:
        r = client.post(f"/api/moodboards/{mbid}/select", {"ids": ids, "note": note}) or {}
    except StudioApiError as e:
        return str(e)
    cores = r.get("palette") or []
    return (f"{r.get('selected', len(ids))} imagem(ns) curada(s) no board `{mbid}`."
            + (f" Paleta: {', '.join(cores)}." if cores else "")
            + "\nGere o prompt de vibe com `moodboard_prompt` ou use o board numa campanha com "
              "`mood_pull`.")


def moodboard_prompt(client: StudioClient, mbid: str, mode: str = "images", instruction: str = "",
                     no_people: bool = True) -> str:
    try:
        r = client.post(f"/api/moodboards/{mbid}/prompt/generate",
                        {"mode": mode, "instruction": instruction, "image_ids": [],
                         "no_people": no_people}) or {}
    except StudioApiError as e:
        # Os dois erros deste caminho pedem conselhos OPOSTOS, e discriminá-los pelo `mode` seria
        # errado: 409 é "não há Claude CLI" (o template resolve); 422 é "não há imagem nenhuma para
        # olhar" — e aí o template *funcionaria*, devolvendo um prompt genérico que esconde do
        # usuário que o board está vazio. Por isso o desvio é pelo status (matriz do FDD §6).
        if e.status == 422:
            return (f"{e}\nImporte candidatas com `moodboard_import` e cure o board com "
                    "`moodboard_pick` antes de gerar o prompt a partir das imagens.")
        if e.status == 409 and mode in ("brief", "images"):
            return f'{e}\nSem o Claude CLI, tente de novo com mode="template".'
        return str(e)
    return f"Prompt de vibe do board `{mbid}` (modo {r.get('mode') or mode}):\n{r.get('prompt', '')}"


def moodboard_delete(client: StudioClient, mbid: str, confirm: bool = False) -> str:
    """Apaga o board inteiro. Destrutivo e irreversível: nunca sem confirmação explícita (ADR-038)."""
    if ui.chat_id():
        ans = ui.confirm(client, f"Apagar o mood board {mbid}?",
                         "Apaga do disco o board inteiro (candidatas, imagens curadas e paleta). "
                         "É irreversível.")
        if not ans.get("answered") or not ans.get("confirmed"):
            return f"Mood board `{mbid}` NÃO foi apagado (o usuário não confirmou)."
    elif not confirm:
        return (f"Apagar um mood board é irreversível. Para apagar `{mbid}`, chame esta tool de "
                "novo com confirm=true.")
    try:
        client.delete(f"/api/moodboards/{mbid}")
    except StudioApiError as e:
        return str(e)
    return (f"Mood board `{mbid}` apagado. Campanhas que já puxaram este board não são afetadas "
            "(a cópia para a campanha é independente).")


def _vibes_params(vibe: str, origem: str, page: int) -> dict:
    """Query do catálogo de vibes, SEM as chaves vazias.

    `origem` é validada no servidor com `if origem is not None`, e o httpx serializa `None` como
    string vazia — mandar `origem=""` viraria 422 ("origem inválida: ''") num caminho em que o
    usuário não filtrou nada. Por isso a chave só entra quando tem valor.
    """
    params: dict = {"page": page}
    if vibe:
        params["vibe"] = vibe
    if origem:
        params["origem"] = origem
    return params


def _filtro_txt(vibe: str, origem: str) -> str:
    partes = [f"{k}={v}" for k, v in (("vibe", vibe), ("origem", origem)) if v]
    return f" (filtro: {', '.join(partes)})" if partes else ""


def vibes_list(client: StudioClient, vibe: str = "", origem: str = "", page: int = 1) -> str:
    """Catálogo de fotos de vibe (`_vibes/`), paginado e filtrável.

    `facets` só é consultada quando NENHUM filtro foi passado: com filtro, a pergunta do usuário já
    é sobre uma vibe específica, e a segunda chamada devolveria as contagens do catálogo inteiro —
    número que contradiz o total da página e confunde o agente.
    """
    try:
        pagina = client.get("/api/vibes", _vibes_params(vibe, origem, page)) or {}
    except StudioApiError as e:
        return str(e)
    total = pagina.get("total", 0)
    if not total:
        return (f"Nenhuma foto de vibe no catálogo{_filtro_txt(vibe, origem)} "
                f"(pasta: {pagina.get('pasta', '?')}).\n"
                "Colete referências com a skill `/mood_vibe_scout` no terminal.")
    linhas = [f"Catálogo de vibes: {total} foto(s), página {pagina.get('page', page)} de "
              f"{pagina.get('pages', 1)}{_filtro_txt(vibe, origem)}."]
    facetas: dict | None = None
    if not vibe and not origem:
        try:
            facetas = client.get("/api/vibes/facets") or {}
        except StudioApiError:
            facetas = None          # enriquecimento: falhar aqui não derruba a listagem
    if facetas is not None:
        nomes = [f"{v.get('nome') or v.get('slug')} ({v.get('total', 0)})"
                 for v in (facetas.get("vibes") or []) if isinstance(v, dict)]
        if nomes:
            linhas.append("Vibes disponíveis: " + ", ".join(nomes) + ".")
        linhas.append(f"Já na peneira: {facetas.get('escolhidas', 0)}. "
                      "Use `vibes_pick` para você escolher as que gosta.")
        return "\n".join(linhas)
    linhas.append("Use `vibes_pick` para você escolher as que gosta.")
    return "\n".join(linhas)


def vibes_pick(client: StudioClient, vibe: str = "", origem: str = "", page: int = 1) -> str:
    """Mostra a página do catálogo na grade e copia para a peneira SÓ o que o usuário escolheu.

    A thumb já vem pronta no campo `url` do item (`/mbfiles/_vibes/<arquivo>`): montar caminho aqui
    seria prefixar o que já está prefixado. O id do catálogo é o NOME DO ARQUIVO (`arquivo`), que é
    o que `POST /api/vibes/select` espera.
    """
    try:
        pagina = client.get("/api/vibes", _vibes_params(vibe, origem, page)) or {}
    except StudioApiError as e:
        return str(e)
    imgs = []
    for item in (pagina.get("items") or []):
        if not isinstance(item, dict):
            continue
        arquivo, url = item.get("arquivo"), item.get("url")
        if not arquivo or not isinstance(url, str) or not url:
            continue
        imgs.append({"id": arquivo, "thumb": url,
                     "label": item.get("vibe_nome") or item.get("vibe") or arquivo})
    if not imgs:
        return (f"Nenhuma foto de vibe nesta página{_filtro_txt(vibe, origem)}. "
                "Veja o que existe com `vibes_list`.")
    ans = ui.choose_images(client, "Escolha as fotos de vibe que você gosta", imgs,
                           minimum=1, maximum=None)
    if ans.get("no_ui"):
        return ("Sem interface para escolher aqui. Fotos de vibe desta página: "
                + ", ".join(i["id"] for i in imgs) + ". Diga quais escolher.")
    if not ans.get("answered"):
        return "O usuário não escolheu (sem resposta). Você pode perguntar de novo."
    ids = ans.get("selected") or []
    if not ids:
        return "O usuário não selecionou nenhuma foto de vibe."
    try:
        r = client.post("/api/vibes/select", {"ids": ids}) or {}
    except StudioApiError as e:
        return str(e)
    copiadas = r.get("copiadas") or []
    duplicadas = r.get("duplicadas") or []
    ausentes = r.get("ausentes") or []
    texto = (f"{len(copiadas)} foto(s) copiada(s) para a peneira; "
             f"{len(duplicadas)} já estava(m) lá")
    # A cláusula de ausentes só aparece quando há ausentes: no caminho feliz, "0 sumiu(ram) do
    # disco" é ruído que o contrato 9 do FDD não tem.
    if ausentes:
        texto += (f"; {len(ausentes)} sumiu(ram) do disco ("
                  + ", ".join(str(a) for a in ausentes) + ")")
    texto += f". Peneira: {r.get('total_escolhidas', '?')}."
    return (texto + "\nUse `escolhidas_list` para ver o caminho da foto-semente e `mood_run` "
            "para rodar a cadeia de mood.")


def escolhidas_list(client: StudioClient, page: int = 1) -> str:
    """A peneira (`_escolhidas/`). O `caminho` absoluto de cada item é o que `mood_run` consome
    como `foto` — é caminho do servidor, não bytes, então não fere a ADR-040."""
    try:
        pagina = client.get("/api/escolhidas", {"page": page}) or {}
    except StudioApiError as e:
        return str(e)
    itens = [i for i in (pagina.get("items") or []) if isinstance(i, dict)]
    total = pagina.get("total", 0)
    if not total:
        return ("A peneira (fotos escolhidas) está vazia. Escolha fotos do catálogo com "
                "`vibes_pick` antes de rodar `mood_run`.")
    linhas = [f"Peneira (fotos escolhidas): {total} no total, página {pagina.get('page', page)} "
              f"de {pagina.get('pages', 1)}."]
    linhas += [f"- `{i.get('arquivo') or i.get('id')}` (caminho: {i.get('caminho', '?')})"
               for i in itens]
    linhas.append("Passe um desses caminhos em `mood_run(foto=...)`.")
    return "\n".join(linhas)


def _erro_do_mood_run(e: StudioApiError) -> str:
    """Repassa o texto do servidor e acrescenta o próximo passo, sem duplicar catálogo nenhum.

    A discriminação é pela mensagem canônica do servidor porque os dois 409 da corrida (Claude CLI
    ausente e corrida em andamento) compartilham o status: sugerir o waiter no caso do CLI mandaria
    o agente esperar um job que nunca começou.
    """
    texto = str(e)
    if e.status == 409 and "em andamento" in texto:
        return f"{texto}\nNão dispare de novo: espere a que está rodando com `mood_run_wait`."
    if e.status == 422 and "nenhuma foto escolhida" in texto:
        return f"{texto}\nEscolha fotos do catálogo de vibes com `vibes_pick`."
    # "foto-semente" sozinho seria largo demais: a mesma expressão aparece no 422 de `board` abaixo
    # do piso ("board precisa ser no mínimo N (a foto-semente já ocupa uma vaga)"), e aí sugerir um
    # caminho de arquivo mandaria o agente procurar o defeito no lugar errado. O casamento é com a
    # frase canônica de `_validar_foto` (`studio/moodboards/mood_run.py`).
    if e.status == 422 and "precisa ser uma das escolhidas" in texto:
        return f"{texto}\nPegue um caminho válido com `escolhidas_list`."
    return texto


def mood_run(client: StudioClient, mbid: str, foto: str = "", objetivos: list[str] | None = None,
             board: int | None = None, n: int | None = None, fundo: str = "",
             confirm: bool = False) -> str:
    """Dispara a cadeia de skills `mood_` sobre uma foto-semente da peneira (ADR-034).

    `estimate` vem SEMPRE antes, em toda execução: a corrida é grátis em crédito, mas baixa dezenas
    de imagens de terceiros e ocupa o Claude CLI por até 1800 s. A barreira é `ui.confirm`, NUNCA
    `ui.confirm_cost`: o sheet de custo é do gate da ADR-016 e usá-lo aqui faria o usuário achar
    que vai pagar.

    `gate` e `saida` não vão no corpo: o primeiro é fixo em `auto` e o segundo é imposto pelo
    servidor (ADR-034).
    """
    alvos = list(objetivos or [])
    # Sem foto-semente o servidor responde 422 de qualquer jeito — mas só DEPOIS de o usuário ter
    # confirmado dezenas de downloads. Gastar a barreira à toa a desvaloriza, então a falta do
    # parâmetro é dita antes de qualquer chamada.
    if not (foto or "").strip():
        return ("Falta a foto-semente da corrida. Pegue um caminho absoluto com `escolhidas_list` "
                "(ou escolha fotos com `vibes_pick` antes) e passe em `mood_run(foto=...)`.")
    try:
        est = client.post(f"/api/moodboards/{mbid}/mood-run/estimate",
                          {"objetivos": alvos, "board": board, "n": n}) or {}
    except StudioApiError as e:
        return _erro_do_mood_run(e)
    downloads = est.get("downloads", "?")
    conta = (f"{est.get('objetivos', len(alvos))} objetivo(s) × "
             f"{est.get('consultas', '?')} consulta(s) × {est.get('n', '?')}")
    if ui.chat_id():
        ans = ui.confirm(client, f"Rodar a cadeia de mood no board {mbid}?",
                         f"Faria até {downloads} download(s) do Pinterest ({conta}). É grátis em "
                         "crédito, mas roda o Claude CLI e pode levar vários minutos.")
        if not ans.get("answered") or not ans.get("confirmed"):
            return (f"Corrida de mood NÃO iniciada no board `{mbid}` (o usuário não confirmou "
                    f"os {downloads} download(s)).")
    elif not confirm:
        return (f"A corrida faria até {downloads} download(s) do Pinterest ({conta}). É grátis em "
                "crédito, mas demorada. Para rodar, chame esta tool de novo com confirm=true.")
    try:
        client.post(f"/api/moodboards/{mbid}/mood-run",
                    {"foto": foto, "objetivos": alvos, "board": board, "n": n,
                     "fundo": fundo or None})
    except StudioApiError as e:
        return _erro_do_mood_run(e)
    return (f"Corrida de mood iniciada no board `{mbid}` ({est.get('objetivos', len(alvos))} "
            f"objetivo(s), até {downloads} download(s), grátis).\n"
            "Ela roda o Claude CLI e pode levar vários minutos: espere com `mood_run_wait`.")


def mood_run_wait(client: StudioClient, mbid: str, timeout: int = 1800,
                  _sleep: Callable[[float], None] = time.sleep) -> str:
    """Espera a corrida de mood e mostra as pranchas no chat.

    O job da corrida tem URL PRÓPRIA (`/api/moodboards/{mbid}/mood-run/job`), diferente da URL de
    job das etapas — por isso NÃO se usa `job_wait` aqui. A corrida não publica progresso
    intermediário (`done` só sobe no fim, mood-run-fdd §7), então o laço só distingue rodando de
    terminado.
    """
    estado, job = _wait_job(client, f"/api/moodboards/{mbid}/mood-run/job",
                            timeout=timeout, _sleep=_sleep)
    if estado == "http":
        return job.get("error", "")
    if estado == "timeout":
        return (f"Board `{mbid}`: a corrida ainda está rodando após {timeout}s "
                "(chame `mood_run_wait` de novo).")
    # `idle` NÃO decide sozinho que não houve corrida: o registro de jobs vive em memória
    # (`studio/common/jobs.py`), então reiniciar o Studio zera o estado enquanto o `_run.json`
    # continua em disco. Quem responde "nunca rodou" é o 404 do `result` (FDD §6), abaixo — sem
    # isso, uma corrida de até 1800 s ficaria inalcançável pelo chat depois de um `make run`.
    if estado == "error":
        cauda = [str(linha) for linha in (job.get("log") or [])][-3:]
        return (f"Board `{mbid}`: a corrida de mood falhou — {job.get('error')}"
                + ("\n" + "\n".join(cauda) if cauda else ""))
    try:
        result = client.get(f"/api/moodboards/{mbid}/mood-run/result") or {}
    except StudioApiError as e:
        return (f"Board `{mbid}`: a corrida terminou, mas não deu para ler as pranchas — {e}"
                if e.status != 404 else
                f"Board `{mbid}`: sem corrida de mood para ler ({e}). Dispare uma com `mood_run`.")
    pranchas = [b for b in (result.get("boards") or []) if isinstance(b, dict)]
    imgs, linhas = [], []
    for b in pranchas:
        rotulo = b.get("objetivo") or b.get("pasta") or "prancha"
        url = b.get("prancha_url")
        if isinstance(url, str) and url:
            imgs.append({"url": url, "label": rotulo, "kind": "image"})
            linhas.append(f"- {rotulo}: prancha pronta ({b.get('imagens', 0)} imagem(ns))")
        else:
            linhas.append(f"- {rotulo}: prancha PENDENTE (declarada no manifesto, "
                          "mas o arquivo não está em disco)")
    if imgs:
        ui.show(client, imgs, f"Pranchas da corrida de mood — board {mbid}")
    cabeca = f"Corrida de mood concluída no board `{mbid}`: {len(pranchas)} prancha(s)."
    rodape = ("Mostrei as pranchas no chat. As imagens baixadas entraram como candidatas: "
              "cure com `moodboard_pick`." if imgs else
              "Nenhuma prancha pronta em disco ainda.")
    return "\n".join([cabeca, *linhas, rodape])


def _erro_do_multishot(saida: str) -> str:
    """Acrescenta o próximo passo ao 409 de "já em andamento" que o `_paid` devolveu como texto.

    A discriminação é pela mensagem canônica do servidor (mesmo motivo de `_erro_do_mood_run`): os
    dois 409 do multishot — Higgsfield sem CLI/login e job em andamento — compartilham o status, e
    sugerir o waiter no caso do login mandaria o agente esperar um job que nunca começou.
    """
    if "em andamento" in saida:
        return f"{saida}\nNão dispare de novo: espere o que está rodando com `moodboard_multishot_wait`."
    return saida


def moodboard_multishot(client: StudioClient, mbid: str, source_id: str, count: int = 4,
                        model: str = "", confirm: bool = False) -> str:
    """Gera ângulos novos de UMA candidata do board — o ÚNICO caminho pago desta frente (ADR-017).

    Passa obrigatoriamente pelo `_paid`: `POST multishot/cost` estima, `ui.confirm_cost` confirma
    com o usuário (ou `confirm=true` no terminal) e só então a rota de geração. Não existe nenhum
    `client.post` solto para essa rota neste módulo: ela só aparece como `gen_path` do `_paid`, e
    é o invariante de gasto da frente (§2 do FDD).

    `follow` faz o texto final apontar `moodboard_multishot_wait`: o job do multishot tem URL
    própria, e `job_wait` só entende `/api/projects/{pid}/{step}/job`.

    O gasto é registrado pelo backend (`action="mood.multishot"`, `spend_pid=None`,
    `spend_step="moodboard"`, ADR-016); esta tool não escreve no ledger.
    """
    corpo = {"source_id": source_id, "count": count, "model": model.strip() or None}
    # O rótulo do modelo é decidido aqui porque o `_paid` recebe `model` ANTES de ver a resposta do
    # cost: quando o usuário não pede um modelo, quem escolhe é o servidor.
    rotulo = model.strip() or "modelo padrão"
    saida = _paid(client, step="moodboard",
                  cost_path=f"/api/moodboards/{mbid}/multishot/cost", cost_body=corpo,
                  gen_path=f"/api/moodboards/{mbid}/multishot/generate", gen_body=corpo,
                  action="Multishot da imagem de vibe do board", model=rotulo, confirm=confirm,
                  follow="moodboard_multishot_wait", model_from_cost=True)
    return _erro_do_multishot(saida)


def moodboard_multishot_wait(client: StudioClient, mbid: str, timeout: int = 600,
                             _sleep: Callable[[float], None] = time.sleep) -> str:
    """Espera o multishot do board e relata quantas candidatas novas entraram.

    Mesma disciplina de `mood_run_wait`: o job tem URL PRÓPRIA
    (`/api/moodboards/{mbid}/multishot/job`), então NÃO se usa `job_wait` aqui.
    """
    estado, job = _wait_job(client, f"/api/moodboards/{mbid}/multishot/job",
                            timeout=timeout, _sleep=_sleep)
    if estado == "http":
        return job.get("error", "")
    if estado == "idle":
        return (f"Board `{mbid}`: nenhum multishot ainda. Dispare um com `moodboard_multishot` "
                "(é pago).")
    if estado == "timeout":
        return (f"Board `{mbid}`: o multishot ainda está rodando após {timeout}s "
                "(chame `moodboard_multishot_wait` de novo).")
    if estado == "error":
        cauda = [str(linha) for linha in (job.get("log") or [])][-3:]
        return (f"Board `{mbid}`: o multishot falhou — {job.get('error')}"
                + ("\n" + "\n".join(cauda) if cauda else ""))
    novas = job.get("added", 0)
    return (f"Multishot do board `{mbid}`: concluído ({job.get('done', 0)}/{job.get('total', 0)}, "
            f"{novas} candidata(s) nova(s)).\n"
            + ("Cure os ângulos novos com `moodboard_pick`." if novas else
               "Nenhuma candidata nova entrou no board."))


def mood_pull(client: StudioClient, pid: str, mbid: str) -> str:
    """Ponte da biblioteca global para a etapa 2 de uma campanha (ADR-013/014).

    Copia as imagens curadas do board para `mood/selected/` da campanha e grava mood.md, paleta e
    vibe. A cópia é INDEPENDENTE do board (apagar o board depois não afeta a campanha) e a operação
    é idempotente. A prontidão da etapa continua vindo do guia do backend (ADR-010), nunca daqui.
    """
    try:
        resp = client.post(f"/api/projects/{pid}/mood/pull/{mbid}") or {}
    except StudioApiError as e:
        texto = str(e)
        if e.status == 422 and "curadas" in texto:
            return f"{texto}\nCure as candidatas do board antes com `moodboard_pick`."
        return texto
    paleta = [c for c in (resp.get("palette") or []) if isinstance(c, str)]
    vibe = (resp.get("vibe") or "").strip()
    partes = [f"Board `{mbid}` puxado para a campanha `{pid}`: "
              f"{resp.get('selected', 0)} imagem(ns) no mood da etapa 2"]
    if vibe:
        partes.append(f', vibe "{vibe}"')
    if paleta:
        partes.append(", paleta " + ", ".join(paleta))
    return ("".join(partes) + ". A cópia é independente do board (apagá-lo depois não afeta a "
            "campanha).\nConfira a prontidão da etapa com `guide_step`.")


# ---------- Personagem e identidade (ADR-039) ----------
def _char_images(cid: str, step: str, cands: Any) -> list[dict]:
    """Mesmo helper de URL das etapas, com base `/cfiles/{cid}` (mount da biblioteca, ADR-039).
    A legenda continua sendo `view`/`name`: personagem não tem lote nem termo de busca."""
    out = []
    for c in _candidate_rows(cands):
        thumb = c.get("thumb")
        if thumb and isinstance(thumb, str) and c.get("id"):
            out.append({"id": c["id"], "thumb": _media_url(f"/cfiles/{cid}", step, thumb),
                        "label": c.get("view") or c.get("name") or ""})
    return out


def _character_prefix(client: StudioClient, pid: str) -> str:
    """Descritor do personagem aplicado à campanha, para reancorar os prompts (ADR-039)."""
    try:
        data = client.get(f"/api/projects/{pid}/character") or {}
    except StudioApiError:
        return ""
    ch = data.get("character") if isinstance(data, dict) else None
    return (ch or {}).get("descriptor", "") if ch else ""


def character_list(client: StudioClient) -> str:
    data = client.get("/api/characters") or []
    if not data:
        return "Nenhum personagem ainda. Crie um com `character_create`."
    return "Personagens:\n" + "\n".join(
        f"- {c['name']} (id `{c['id']}`, {c.get('style', 'foto')})"
        + (" — fixado" if c.get("locked_ref") else " — a fixar") for c in data)


def character_create(client: StudioClient, name: str, style: str = "foto") -> str:
    c = client.post("/api/characters", {"name": name, "style": style})
    return f"Personagem '{c['name']}' criado (id `{c['id']}`). Explore variações com `character_explore`."


def character_explore(client: StudioClient, cid: str, brief: str, count: int = 6) -> str:
    if not brief.strip():
        return "Escreva um brief do personagem (em inglês)."
    try:
        client.post(f"/api/characters/{cid}/explore", {"brief": brief, "count": count})
    except StudioApiError as e:
        return str(e)
    return (f"Explorando {count} variações no motor local (grátis). É GPU, leva alguns minutos — "
            "espere com `character_wait` e então use `character_pick`.")


def character_wait(client: StudioClient, cid: str, timeout: int = 900, _sleep=time.sleep) -> str:
    """Espera o job do personagem (explore/sheet) terminar. O job de personagem tem URL própria
    (`/api/characters/{cid}/job`), diferente da URL de job das etapas — por isso NÃO use `job_wait`."""
    deadline = time.monotonic() + max(1, timeout)
    viu_running = False
    while time.monotonic() < deadline:
        try:
            g = client.get(f"/api/characters/{cid}/job")
        except StudioApiError as e:
            return str(e)
        state = g.get("state", "idle")
        if state == "running":
            viu_running = True
            _sleep(2.0)
            continue
        if state == "idle" and not viu_running:
            return f"Personagem {cid}: nenhum trabalho em andamento."
        if g.get("error"):
            return f"Personagem {cid}: o job falhou — {g['error']}"
        return f"Personagem {cid}: {g.get('mode', 'job')} concluído ({g.get('added', 0)}/{g.get('total', 0)})."
    return f"Personagem {cid}: ainda gerando após {timeout}s (rode `character_wait` de novo)."


def character_pick(client: StudioClient, cid: str) -> str:
    """Mostra as variações para o USUÁRIO escolher o personagem e o fixa (gera o descritor)."""
    try:
        cands = client.get(f"/api/characters/{cid}/candidates", {"step": "explore"}) or []
    except StudioApiError as e:
        return str(e)
    imgs = _char_images(cid, "explore", cands)
    if not imgs:
        try:
            job = client.get(f"/api/characters/{cid}/job")
        except StudioApiError:
            job = {}
        if job.get("state") == "running":
            return (f"Ainda gerando as variações ({job.get('added', 0)}/{job.get('total', 0)}). "
                    "Espere com `character_wait` e chame de novo.")
        if job.get("error"):
            return f"A exploração falhou: {job['error']} (o motor local/ComfyUI está no ar?)."
        return "Nenhuma variação ainda — rode `character_explore` antes."
    ans = ui.choose_images(client, "Escolha o personagem (o que você acertou)", imgs, minimum=1, maximum=1)
    if ans.get("no_ui"):
        return "Sem interface aqui. Variações: " + ", ".join(i["id"] for i in imgs) + ". Diga qual fixar."
    if not ans.get("answered") or not ans.get("selected"):
        return "O usuário não escolheu o personagem."
    escolhido = ans["selected"][0]
    try:
        meta = client.post(f"/api/characters/{cid}/lock", {"candidate_id": escolhido, "step": "explore"}) or {}
    except StudioApiError as e:
        return str(e)   # mesma regra dos picks de etapa: erro vira texto acionável, sem sufixo JSON
    # `next_step` é `null`: personagem é biblioteca global (ADR-039), fora da cadeia das 10 etapas —
    # a chave fica no sufixo para o shape ser único nas 5 `*_pick`.
    return (f"Personagem fixado. Descritor de identidade:\n{meta.get('descriptor', '(gerado)')}"
            f"\n{_result_json([escolhido], None)}")


def character_sheet(client: StudioClient, cid: str) -> str:
    try:
        client.post(f"/api/characters/{cid}/sheet", {})
    except StudioApiError as e:
        return str(e)
    return "Gerando o character sheet (frente, 3/4, perfil, corpo inteiro) no motor local. Espere com `character_wait`."


def character_apply(client: StudioClient, pid: str, cid: str) -> str:
    try:
        client.post(f"/api/projects/{pid}/character", {"cid": cid})
    except StudioApiError as e:
        return str(e)
    return ("Personagem aplicado à campanha. A partir de agora eu injeto o descritor de identidade "
            "nos prompts das etapas 3–5, para manter a mesma pessoa entre as cenas.")


def character_bind_soul(client: StudioClient, cid: str, variant: str = "soul-2") -> str:
    """Treina um Soul ID (Higgsfield, PAGO — plano Basic+) para identidade em foto/vídeo."""
    if ui.chat_id():
        ans = ui.confirm(client, "Treinar Soul ID (Higgsfield, plano pago)",
                         "Treina um modelo de identidade da pessoa. Requer plano Basic+ na Higgsfield.")
        if not ans.get("answered") or not ans.get("confirmed"):
            return "Treino de Soul cancelado pelo usuário."
    try:
        client.post(f"/api/characters/{cid}/soul", {"variant": variant})
    except StudioApiError as e:
        return str(e)
    return f"Soul treinado ({variant}). A identidade paga fica disponível para gerar com `--soul-id`."


def character_score(client: StudioClient, cid: str, candidate_id: str, step: str = "explore") -> str:
    try:
        res = client.post(f"/api/characters/{cid}/score", {"candidate_id": candidate_id, "step": step})
    except StudioApiError as e:
        return str(e)
    if not res.get("available"):
        return f"Nota de identidade indisponível: {res.get('reason')}"
    return f"Nota de identidade (similaridade facial): {res.get('score')}"
