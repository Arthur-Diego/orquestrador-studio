"""[extensão] Validador de congruência do roteiro — o guardião do "total sentido".

O schema (Pydantic) garante a ESTRUTURA. Este módulo garante a COERÊNCIA entre campos: numeração
contígua, `scene_key` do plano batendo com a cena, beats cobrindo a duração do plano, segments de
narração espelhando os planos, e as somas (duração/palavras) dentro do alvo. É a checagem que a
skill roda como gate antes de materializar no ContentFlow.

Funções puras (sem rede), testáveis. `erros` bloqueiam; `avisos` só alertam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import ORDEM_CENAS, Roteiro

#: Tolerância relativa para somas (duração/palavras) vs. alvo — o schema fala em ±3%.
TOLERANCIA = 0.05


@dataclass
class RelatorioValidacao:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros

    def resumo(self) -> str:
        if self.ok and not self.avisos:
            return "congruência OK — roteiro coerente."
        linhas = [f"✗ {e}" for e in self.erros] + [f"○ {a}" for a in self.avisos]
        cab = "congruência OK (com avisos):" if self.ok else "roteiro INCONGRUENTE:"
        return cab + "\n" + "\n".join(f"  {ln}" for ln in linhas)


def _aprox(a: float, b: float, tol: float = TOLERANCIA) -> bool:
    """True se `a` está a ±tol relativos de `b` (com piso absoluto p/ alvos pequenos)."""
    return abs(a - b) <= max(tol * abs(b), 0.5)


def validar_congruencia(r: Roteiro) -> RelatorioValidacao:
    rel = RelatorioValidacao()
    planos = r.planos

    # 1. Numeração global contígua 1..N na ordem das cenas (= StoryboardShot.n).
    esperado = list(range(1, len(planos) + 1))
    obtido = [p.n for p in planos]
    if obtido != esperado:
        rel.erros.append(f"plano.n deve ser contíguo 1..{len(planos)} na ordem das cenas; obtido {obtido}")

    # 2. scene_key de cada plano bate com a cena que o contém.
    for cena in r.cenas:
        for p in cena.planos:
            if p.scene_key != cena.key:
                rel.erros.append(f"plano {p.n}: scene_key '{p.scene_key}' ≠ cena '{cena.key}'")

    # 3. Cenas: chaves únicas e na ordem imutável (subsequência de gancho→…→cta).
    chaves = [c.key for c in r.cenas]
    if len(set(chaves)) != len(chaves):
        rel.erros.append(f"cenas com key repetida: {chaves}")
    posicoes = [ORDEM_CENAS.index(k) for k in chaves]
    if posicoes != sorted(posicoes):
        rel.erros.append(f"cenas fora da ordem gancho→problema→virada→prova→cta: {chaves}")

    # 4. Beats cobrem a duração do plano (multi_prompt): Σ seconds ≈ duration_s; nenhum beat maior.
    for p in planos:
        soma_beats = sum(b.seconds for b in p.video_prompt.beats)
        if not _aprox(soma_beats, p.duration_s):
            rel.erros.append(
                f"plano {p.n}: beats somam {soma_beats:.1f}s mas o plano dura {p.duration_s:.1f}s")
        for b in p.video_prompt.beats:
            if b.seconds > p.duration_s + 0.01:
                rel.erros.append(f"plano {p.n}: beat de {b.seconds:.1f}s excede a duração do plano")

    # 5. Somas do vídeo vs. alvo/meta.
    soma_dur = sum(p.duration_s for p in planos)
    if not _aprox(soma_dur, r.meta.target_duration_s):
        rel.erros.append(
            f"duração total {soma_dur:.1f}s fora de ±{int(TOLERANCIA*100)}% do alvo "
            f"{r.meta.target_duration_s}s")
    if not _aprox(soma_dur, r.meta.duracao_total_s):
        rel.avisos.append(
            f"meta.duracao_total_s={r.meta.duracao_total_s} ≠ soma dos planos {soma_dur:.1f}s")
    soma_palavras = sum(p.palavras for p in planos)
    if not _aprox(soma_palavras, r.meta.palavras_total):
        rel.avisos.append(
            f"meta.palavras_total={r.meta.palavras_total} ≠ soma das palavras dos planos {soma_palavras}")

    # 6. Narração: um segment por plano, plano_n e scene_key batendo, texto = narração do plano.
    por_n = {p.n: p for p in planos}
    segs = r.narracao_completa.segments
    if len(segs) != len(planos):
        rel.erros.append(f"narracao_completa.segments tem {len(segs)} itens; esperado {len(planos)} (1/plano)")
    for s in segs:
        p = por_n.get(s.plano_n)
        if p is None:
            rel.erros.append(f"segment aponta plano_n {s.plano_n} inexistente")
            continue
        if s.scene_key != p.scene_key:
            rel.erros.append(f"segment do plano {s.plano_n}: scene_key '{s.scene_key}' ≠ plano '{p.scene_key}'")
        if s.text.strip() != p.narration.strip():
            rel.avisos.append(f"segment do plano {s.plano_n}: texto diverge da narração do plano")

    # 7. Identidade consistente: o bloco de estilo é reusado no início de cada image_prompt (aviso).
    estilo = r.identidade_visual.estilo.strip()
    if estilo:
        fora = [p.n for p in planos if estilo[:24].lower() not in p.image_prompt.lower()]
        if fora:
            rel.avisos.append(f"planos sem o bloco de estilo no image_prompt (identidade): {fora}")

    # 8. Virada é o maior bloco (regra do método): Σ duração da virada ≥ das outras cenas.
    dur_por_cena = {c.key: sum(p.duration_s for p in c.planos) for c in r.cenas}
    if "virada" in dur_por_cena:
        maior = max(dur_por_cena.values())
        if dur_por_cena["virada"] < maior:
            rel.avisos.append("a cena 'virada' não é o maior bloco de duração")

    return rel
