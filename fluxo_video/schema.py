"""[extensão] Schema canônico do roteiro rico (RoteiroPro v1.0).

Espelha `making-money/.claude/skills/roteiro-pro/schema.json` em Pydantic v2. É a FONTE DA
VERDADE do formato `cenas → planos → {image_prompt, video_prompt{beats}}` — o mesmo objeto que
o ContentFlow materializa em StoryboardShot / SlideSpec / VideoScene / layout.master_caption.

`extra="forbid"` reproduz `additionalProperties:false` do JSON Schema: um roteiro com campo
desconhecido é rejeitado, não silenciosamente aceito.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SceneKey = Literal["gancho", "problema", "virada", "prova", "cta"]
#: Ordem imutável dos blocos narrativos (Gancho→Problema→Virada→Prova→CTA).
ORDEM_CENAS: tuple[SceneKey, ...] = ("gancho", "problema", "virada", "prova", "cta")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VideoBeat(_Base):
    seconds: float = Field(ge=1)
    prompt: str


class VideoPrompt(_Base):
    subject: str
    subject_movement: str
    scene_description: str
    camera: str  # UM movimento por plano
    lighting: str
    atmosphere: str
    beats: list[VideoBeat] = Field(min_length=1)  # cobrem TODOS os segundos do plano
    negative_extra: str


class Plano(_Base):
    n: int = Field(ge=1)  # global e sequencial no vídeo (= StoryboardShot.n)
    scene_key: SceneKey
    duration_s: float = Field(ge=2.0, le=15.0)
    palavras: int = Field(ge=12, le=18)
    narration: str
    headline: str
    body: str
    visual: str
    image_prompt: str
    image_negative: str
    video_prompt: VideoPrompt
    transicao: str
    sfx: str
    personagem: bool = True
    """Este plano mostra o personagem-âncora? Se True e a identidade estiver ligada, a imagem
    do plano é gerada com a referência fixa do personagem (IPAdapter). Cenas de cenário puro
    (sem o personagem) usam False para não injetar um rosto onde não deve haver."""


class Cena(_Base):
    key: SceneKey
    label: str
    objetivo: str
    planos: list[Plano] = Field(min_length=1)


class Personagem(_Base):
    nome: str
    descriptor: str
    negative: str


class IdentidadeVisual(_Base):
    estilo: str  # bloco EN reutilizado VERBATIM no início de todo image_prompt/video_prompt
    paleta: str
    personagem: Personagem
    negative_base: str
    ancora: str


class Meta(_Base):
    titulo: str
    essencia: str
    content_type: Literal["reel", "story"]
    aspect_ratio: Literal["9:16"]
    target_duration_s: int = Field(ge=15, le=600)
    duracao_total_s: float
    palavras_total: int
    persona: str
    tom: str
    idioma: Literal["pt-BR"]


class NarracaoSegment(_Base):
    plano_n: int
    scene_key: SceneKey
    text: str


class NarracaoCompleta(_Base):
    texto: str
    segments: list[NarracaoSegment]


class Publicacao(_Base):
    legenda_post: str
    hashtags: list[str] = Field(max_length=8)
    cta_unico: str


class Audio(_Base):
    voz_sugerida: str
    musica: str
    sfx_gerais: str


class Fonte(_Base):
    ref: str
    status: Literal["fornecida", "verificada", "FONTE NECESSÁRIA"]
    uso: str


class ValidacaoPorPlano(_Base):
    n: int
    ok: bool
    notas: str


class ValidacaoConjunto(_Base):
    progressao_sem_repeticao: bool
    prova_responde_gancho: bool
    cta_unico: bool
    duracao_ok: bool
    palavras_ok: bool
    virada_maior_bloco: bool
    identidade_consistente: bool
    essencia_preservada: bool
    notas: str


class Validacao(_Base):
    por_plano: list[ValidacaoPorPlano]
    conjunto: ValidacaoConjunto
    aprovado_para_producao: bool


class Roteiro(_Base):
    version: Literal["1.0"]
    meta: Meta
    identidade_visual: IdentidadeVisual
    cenas: list[Cena] = Field(min_length=3, max_length=5)
    narracao_completa: NarracaoCompleta
    publicacao: Publicacao
    audio: Audio
    fontes: list[Fonte]
    validacao: Validacao

    @property
    def planos(self) -> list[Plano]:
        """Todos os planos, na ordem das cenas (a lista plana equivalente aos StoryboardShots)."""
        return [p for cena in self.cenas for p in cena.planos]


class RoteiroInvalido(ValueError):
    """Erro de leitura/estrutura de um roteiro (mensagem curta, sem stacktrace cru)."""


def carregar_roteiro(caminho: Path | str) -> Roteiro:
    """Lê e valida um roteiro rico em JSON. Erros viram `RoteiroInvalido` legível."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise RoteiroInvalido(f"roteiro não encontrado: {caminho}")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RoteiroInvalido(f"JSON inválido em {caminho.name}: {exc}") from exc
    return validar_estrutura(dados)


def validar_estrutura(dados: dict) -> Roteiro:
    """Valida um dict contra o schema. `RoteiroInvalido` com as falhas resumidas."""
    try:
        return Roteiro.model_validate(dados)
    except ValidationError as exc:
        linhas = [f"  · {'/'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise RoteiroInvalido("roteiro fora do schema RoteiroPro v1.0:\n" + "\n".join(linhas)) from exc
