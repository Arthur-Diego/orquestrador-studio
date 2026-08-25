"""Guia da etapa 11 (aula 001 = 016) — leitura pura dos artefatos do projeto.

O portfólio que destrava esta etapa é **global** (ADR-012): o projeto criado para o negócio do
lead nunca terá quatro vídeos publicados, então contar dentro dele deixava a etapa inutilizável
(auditoria 11.2). O teaser sai de um take deste projeto; o portfólio, de todos os outros.
"""
from __future__ import annotations

from datetime import date, datetime

from ...common.guide import Guide, exists
from ...prospect import service as prospect
from . import META

#: Aula 001: a DM não pode levar link — DM com link cai em spam.
LINK_MARKS = ("http://", "https://", "www.")
#: `[extensão]`: follow-up pendente quando a resposta veio há mais de uma semana sem call.
CALL_WINDOW_DAYS = 7

WHAT = (
    "Com quatro vídeos publicados no perfil, todo dia encontre 10 pequenos negócios no "
    "Instagram (clínicas, academias, advogados, estética, dentistas, comércios) e mande uma DM "
    "personalizada: mostre que olhou o perfil e cite um post específico — é isso que faz não ser "
    "spam. O script tem três ideias (você acompanha a marca, um post ressoou, você cria anúncios "
    "criativos e o portfólio está no perfil) e o gancho: \"Tive uma inspiração e criei algo para "
    "o seu negócio. Quer ver como ficou?\". Você só cria de verdade se a empresa responder: aí "
    "produz 5 a 10 segundos com música e impacto, envia e chama para uma call de 15 minutos — "
    "crie um projeto para o negócio do lead e percorra as etapas 1 a 6 em versão curta (uma cena "
    "basta): o teaser sai de um take desse projeto, e o portfólio vem dos projetos anteriores. Na "
    "call você não vende IA, vende resultado: mostre as etapas de produção, ancore valor por "
    "etapa até o total, ofereça condição especial na hora (ou por 24h), 50 % na entrada e 50 % na "
    "entrega. No começo, cobre R$ 100 a R$ 500 por vídeo de 30 s a 1 min para girar volume e "
    "construir portfólio real."
)
CHECKLIST = [
    "Portfólio de 4 vídeos publicado antes da primeira DM.",
    "10 DMs hoje, cada uma citando um post específico do negócio; sem links.",
    "Teaser só para quem respondeu; 5 a 10 s, com música e impacto.",
    "Call de 15 min marcada; na call: lista de etapas, valores por etapa → total, urgência, "
    "50/50, 50 % off no 1º com valor cheio explícito.",
    "Vendi resultado (mais clientes para o negócio), não \"IA\".",
]


def _leads(root) -> list[dict]:
    """Leads do projeto; `leads.json` corrompido vira lista vazia (o guia nunca explode a tela)."""
    try:
        return prospect.load_leads(root)
    except (ValueError, OSError):
        return []


def _dias(iso: str) -> int | None:
    try:
        return (date.today() - datetime.fromisoformat(iso).date()).days
    except (TypeError, ValueError):
        return None


def guide(pid: str) -> dict:
    from ...refs.service import project_dir
    root = project_dir(pid)
    gate = prospect.gate(root)
    leads = _leads(root)
    enviadas = [x for x in leads if x.get("sent_at")]
    responderam = [x for x in leads if x.get("replied")]
    com_teaser = [x for x in leads if x.get("teaser")]
    hoje = prospect.today_sent(leads)
    pitch = prospect.load_pitch_values(root)

    g = Guide(META).text(WHAT, CHECKLIST)

    g.input("portfolio", f"Portfólio global de {gate['required']} vídeos publicados", gate["ok"],
            detail=f"{gate['published']}/{gate['required']} projetos com post registrado",
            fix="Publique quatro vídeos diferentes (um por projeto) na etapa 10", step="publish")

    g.output("leads", "prospect/leads.json com leads cadastrados", bool(leads),
             detail=f"{len(leads)} lead(s)" if leads else "cadastre os pequenos negócios que você já acompanha")
    g.output("dms", "DMs marcadas como enviadas", bool(enviadas),
             detail=f"{len(enviadas)} enviada(s)")
    pendentes = [x for x in responderam if not x.get("teaser")]
    g.output("teasers", "Teaser de 5 a 10 s para quem respondeu", bool(com_teaser) and not pendentes,
             detail=(f"{len(com_teaser)} teaser(s)" + (f", {len(pendentes)} responderam e ainda esperam"
                                                       if pendentes else ""))
             if responderam else "ninguém respondeu ainda — a aula manda criar só depois da resposta")
    g.output("pitch", "prospect/pitch.md com as etapas e os valores", exists(pid, "prospect/pitch.md"),
             detail="ancoragem por etapa até o total que você quer cobrar")

    # --- validações (nunca bloqueiam) ---
    if hoje >= prospect.DAILY_LIMIT:
        g.check("dms_hoje", f"{prospect.DAILY_LIMIT} DMs hoje (aula 001)", "ok", detail=f"{hoje} hoje")
    else:
        g.check("dms_hoje", f"{prospect.DAILY_LIMIT} DMs hoje (aula 001)", "warn" if hoje else "todo",
                detail=f"{hoje}/{prospect.DAILY_LIMIT} hoje",
                fix="a meta é disciplina diária, não trava: o Studio conta e avisa")

    sem_post = [x for x in leads if not (x.get("post_ref") or "").strip()]
    com_link = [x for x in leads if any(m in (x.get("dm_text") or "").lower() for m in LINK_MARKS)]
    if not leads:
        g.check("dm_personalizada", "DM cita um post específico e não leva link", "todo")
    elif sem_post or com_link:
        g.check("dm_personalizada", "DM cita um post específico e não leva link", "fail",
                detail=(f"{len(sem_post)} sem post citado; " if sem_post else "")
                       + (f"{len(com_link)} com link" if com_link else "").strip("; "),
                fix="é o que faz não ser spam: mostre que olhou o perfil e cite um post")
    else:
        g.check("dm_personalizada", "DM cita um post específico e não leva link", "ok")

    fora_de_ordem = [x for x in leads if x.get("teaser") and not x.get("replied")]
    g.check("teaser_apos_resposta", "Teaser só depois que a empresa responder",
            "fail" if fora_de_ordem else "ok",
            detail=f"{len(fora_de_ordem)} teaser(s) antes da resposta" if fora_de_ordem else
            "\"você só cria de verdade se a empresa responder\" (aula 001)")

    if not pitch["priced"]:
        g.check("pitch_valores", "Valor por etapa preenchido (ancoragem)", "todo",
                detail="revele o valor etapa por etapa até chegar no total que você quer cobrar")
    elif not pitch["matches"]:
        g.check("pitch_valores", "Soma das etapas igual ao total", "warn",
                detail=f"etapas somam R$ {pitch['sum']:.2f}, total R$ {pitch['total']:.2f}",
                fix="a ancoragem só funciona se as contas fecharem")
    else:
        g.check("pitch_valores", "Soma das etapas igual ao total", "ok",
                detail=f"total R$ {pitch['total']:.2f} · com 50 % off R$ {pitch['discount']:.2f}")

    if not pitch["priced"]:
        g.check("pitch_faixa", "Faixa inicial de R$ 100 a R$ 500 (aula 016)", "todo")
    else:
        g.check("pitch_faixa", "Faixa inicial de R$ 100 a R$ 500 (aula 016)",
                "ok" if pitch["in_range"] else "warn", detail=f"total R$ {pitch['total']:.2f}",
                fix=None if pitch["in_range"] else
                "no começo a aula manda cobrar R$ 100 a R$ 500 por vídeo de 30 s a 1 min")

    # A janela conta a partir da RESPOSTA (`replied_at`); leads antigos, gravados antes do
    # campo existir, caem no `sent_at` — é o melhor dado disponível para eles.
    atrasados = [x for x in responderam
                 if not x.get("call_at")
                 and (d := _dias(x.get("replied_at") or x.get("sent_at") or "")) is not None
                 and d > CALL_WINDOW_DAYS]
    g.check("followup", "Call marcada em até 7 dias da resposta `[extensão]`",
            "warn" if atrasados else ("ok" if responderam else "todo"),
            detail=f"{len(atrasados)} lead(s) responderam e seguem sem call" if atrasados else None,
            fix="mande o follow-up: \"podemos agendar uma call de 15 minutinhos\"" if atrasados else None)

    return g.build()
