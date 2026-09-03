"""Manifesto de parâmetros das skills `mood_` `[extensão]` (ADH-OS-20260902-04).

A tela não pode ter campo hardcoded: cada parâmetro novo numa skill obrigaria a mexer no
front, e as duas verdades divergiriam em silêncio. Este módulo é a fonte única do formulário —
o front pergunta `GET /api/skills/mood/params` e desenha exatamente o que vier.

## As duas camadas (é o que torna o teste de divergência honesto)

* **Camada declarada** — `flag`, `posicional`, `tipo`, `opcoes`, `agregador` e `default`. É o que
  o `SKILL.md` da skill realmente declara. `tests/test_skills_params.py` extrai esses mesmos
  campos dos `SKILL.md` e **falha** se divergirem em qualquer direção (parâmetro a mais no
  manifesto, parâmetro a mais na skill, default diferente, opção de enum diferente).
* **Camada de apresentação** — `Apresentacao`: `rotulo`, `ajuda`, `grupo`, `min`, `max` e
  `obrigatorio_em_auto`. **Nenhum `SKILL.md` declara essas chaves** — são decisão de UI e moram
  só aqui. O teste **não** as compara com o `SKILL.md`; cobrá-las de um documento que não as
  declara transformaria o teste em teatro (o autor acabaria afrouxando a comparação inteira
  para fazê-la passar).

## Regras de consumo (valem para o front e para quem mais consumir o manifesto)

* `default` é **placeholder, nunca valor pré-preenchido**. Campo vazio não é enviado à skill, e
  a skill cai no default dela. É o que faz "controle total" e "modo default" serem o mesmo
  caminho de código.
* `default is None` significa "o `SKILL.md` não declara default", não "o default é vazio".
  Na `mood_board_builder` isso é a regra, não a exceção: ela declara os mesmos flags do
  orquestrador sem defaults próprios (herda na prática).
* `obrigatorio_em_auto` só existe porque, com `--gate auto`, a skill não tem como perguntar:
  em `claude -p` não existe `AskUserQuestion`. Confirmado por spike em 2026-09-02 — a
  `mood_orquestrador` roda em `-p` e **para sozinha** dizendo o que falta quando o insumo
  obrigatório não vem. O manifesto marca o campo para a tela avisar antes de gastar a corrida.

A `mood_visual_dna` **não entra**: o `SKILL.md` dela não tem seção de Invocação nem parâmetro
de linha de comando (é invocada como subskill com a imagem e o objetivo).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MANIFESTO_VERSAO = 1

Tipo = Literal["enum", "multi", "inteiro", "texto", "caminho", "lista", "booleano"]
Grupo = Literal["principal", "avancado"]


@dataclass(frozen=True, slots=True)
class Apresentacao:
    """Camada de apresentação de um parâmetro — decisão de UI, não declarada no `SKILL.md`.

    Args:
        rotulo: nome do campo na tela.
        ajuda: texto curto abaixo do campo.
        grupo: `principal` fica visível; `avancado` fica recolhido.
        minimo: piso sugerido para `tipo="inteiro"` (dica de UI, não validação da skill).
        maximo: teto sugerido para `tipo="inteiro"`; `None` quando a skill não impõe teto.
        obrigatorio_em_auto: a tela deve exigir preenchimento quando `gate == "auto"`.
    """

    rotulo: str
    ajuda: str = ""
    grupo: Grupo = "avancado"
    minimo: int | None = None
    maximo: int | None = None
    obrigatorio_em_auto: bool = False

    def to_dict(self) -> dict[str, object]:
        # As chaves `min`/`max` são as do contrato publicado; os atributos são `minimo`/`maximo`
        # porque `min`/`max` sombreariam builtins (guidelines §5).
        return {
            "rotulo": self.rotulo,
            "ajuda": self.ajuda,
            "grupo": self.grupo,
            "min": self.minimo,
            "max": self.maximo,
            "obrigatorio_em_auto": self.obrigatorio_em_auto,
        }


@dataclass(frozen=True, slots=True)
class Param:
    """Um parâmetro exposto ao front: camada declarada + camada de apresentação.

    Args:
        nome: chave enviada pela tela (e chave do JSON de `--params`).
        tipo: como a tela desenha e serializa o campo.
        apresentacao: rótulo, ajuda, grupo e limites de UI.
        flag: a flag de linha de comando; `None` para parâmetro só posicional.
        posicional: a skill também aceita este valor como argumento posicional.
        opcoes: valores literais aceitos, quando `tipo` é `enum` ou `multi`.
        agregador: literal que a skill aceita no lugar da lista inteira (ex.: `todos`).
        default: default **declarado no `SKILL.md`**; `None` quando não há default declarado.
    """

    nome: str
    tipo: Tipo
    apresentacao: Apresentacao
    flag: str | None = None
    posicional: bool = False
    opcoes: tuple[str, ...] = ()
    agregador: str | None = None
    default: str | int | bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "nome": self.nome,
            "flag": self.flag,
            "posicional": self.posicional,
            "tipo": self.tipo,
            "opcoes": list(self.opcoes),
            "agregador": self.agregador,
            "default": self.default,
            "apresentacao": self.apresentacao.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ParamIgnorado:
    """Flag que a skill declara e o manifesto deliberadamente NÃO expõe como campo.

    Existe para que "sumiu do manifesto" nunca seja silencioso: o teste de divergência aceita
    uma flag ausente apenas se ela estiver listada aqui, com motivo.
    """

    flag: str
    motivo: str

    def to_dict(self) -> dict[str, str]:
        return {"flag": self.flag, "motivo": self.motivo}


@dataclass(frozen=True, slots=True)
class Skill:
    """Uma skill `mood_` parametrizável pela tela."""

    nome: str
    rotulo: str
    resumo: str
    skill_md: str
    params: tuple[Param, ...]
    ignorados: tuple[ParamIgnorado, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "nome": self.nome,
            "rotulo": self.rotulo,
            "resumo": self.resumo,
            "skill_md": self.skill_md,
            "params": [p.to_dict() for p in self.params],
            "parametros_ignorados": [i.to_dict() for i in self.ignorados],
        }


_OBJETIVOS = ("ambiente", "campanha", "produto", "personagem")
_GATE = ("interativo", "auto")
_FUNDO = ("escuro", "claro")

_ORQUESTRADOR = Skill(
    nome="mood_orquestrador",
    rotulo="Orquestrador do mood",
    resumo="Foto escolhida → DNA visual → prancha, um board por objetivo.",
    skill_md=".claude/skills/mood_orquestrador/SKILL.md",
    params=(
        Param(
            nome="foto",
            flag="--foto",
            posicional=True,
            tipo="caminho",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Foto-semente",
                ajuda="caminho do arquivo, trecho do nome ou diretório; sem ela a skill pergunta",
                grupo="principal",
                obrigatorio_em_auto=True,
            ),
        ),
        Param(
            nome="objetivo",
            flag="--objetivo",
            tipo="multi",
            opcoes=_OBJETIVOS,
            agregador="todos",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Objetivos",
                ajuda="um board por objetivo marcado",
                grupo="principal",
                obrigatorio_em_auto=True,
            ),
        ),
        Param(
            nome="gate",
            flag="--gate",
            tipo="enum",
            opcoes=_GATE,
            default="interativo",
            apresentacao=Apresentacao(
                rotulo="Aprovação humana",
                ajuda="auto = a skill decide sozinha e registra em arquivo; é o único modo viável pela tela",
                grupo="principal",
            ),
        ),
        Param(
            nome="board",
            flag="--board",
            tipo="inteiro",
            default=8,
            apresentacao=Apresentacao(
                rotulo="Imagens por prancha",
                ajuda="a foto-semente já ocupa uma vaga: consultas = board − 1",
                minimo=4,
            ),
        ),
        Param(
            nome="n",
            flag="--n",
            tipo="inteiro",
            default=3,
            apresentacao=Apresentacao(
                rotulo="Candidatas por consulta",
                ajuda="downloads = objetivos × (board − 1) × n",
                minimo=1,
            ),
        ),
        Param(
            nome="fundo",
            flag="--fundo",
            tipo="enum",
            opcoes=_FUNDO,
            default="escuro",
            apresentacao=Apresentacao(rotulo="Fundo da prancha"),
        ),
        Param(
            nome="saida",
            flag="--saida",
            tipo="caminho",
            default="processo_manual/moodboard/",
            apresentacao=Apresentacao(
                rotulo="Pasta de saída",
                ajuda="é a raiz; cada objetivo ganha uma subpasta própria",
            ),
        ),
    ),
    ignorados=(
        ParamIgnorado(
            flag="--params",
            motivo=(
                "é o próprio mecanismo pelo qual a tela entrega os outros parâmetros "
                "(JSON com as mesmas chaves); expor como campo do formulário seria circular"
            ),
        ),
    ),
)

_BOARD_BUILDER = Skill(
    nome="mood_board_builder",
    rotulo="Montador de prancha",
    resumo="A partir do DNA: busca, baixa, cura e monta uma prancha — um objetivo por corrida.",
    skill_md=".claude/skills/mood_board_builder/SKILL.md",
    params=(
        Param(
            nome="dna",
            flag="--dna",
            tipo="caminho",
            default=None,
            apresentacao=Apresentacao(
                rotulo="DNA visual (JSON)",
                ajuda="saída da mood_visual_dna — é o caminho normal; sem ele informe a foto",
                grupo="principal",
            ),
        ),
        Param(
            nome="foto",
            flag="--foto",
            tipo="caminho",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Foto-semente",
                ajuda="alternativa ao DNA: a skill produz o DNA antes de montar",
                grupo="principal",
            ),
        ),
        Param(
            nome="objetivo",
            flag="--objetivo",
            tipo="enum",
            opcoes=_OBJETIVOS,
            default=None,
            apresentacao=Apresentacao(
                rotulo="Objetivo",
                ajuda="um só — quem monta vários numa corrida é a mood_orquestrador",
                grupo="principal",
            ),
        ),
        Param(
            nome="gate",
            flag="--gate",
            tipo="enum",
            opcoes=_GATE,
            default="interativo",
            apresentacao=Apresentacao(
                rotulo="Aprovação humana",
                ajuda="auto decide a curadoria sozinho e registra em curadoria.md",
                grupo="principal",
            ),
        ),
        Param(
            nome="board",
            flag="--board",
            tipo="inteiro",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Imagens por prancha",
                ajuda="sem default próprio no SKILL.md — na prática herda o 8 da mood_orquestrador",
                minimo=4,
            ),
        ),
        Param(
            nome="n",
            flag="--n",
            tipo="inteiro",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Candidatas por consulta",
                ajuda="sem default próprio no SKILL.md — na prática herda o 3 da mood_orquestrador",
                minimo=1,
            ),
        ),
        Param(
            nome="fundo",
            flag="--fundo",
            tipo="enum",
            opcoes=_FUNDO,
            default=None,
            apresentacao=Apresentacao(
                rotulo="Fundo da prancha",
                ajuda="sem default próprio no SKILL.md — na prática herda `escuro`",
            ),
        ),
        Param(
            nome="saida",
            flag="--saida",
            tipo="caminho",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Pasta de saída",
                ajuda="sem default próprio no SKILL.md — na prática herda a raiz da mood_orquestrador",
            ),
        ),
    ),
)

_VIBE_SCOUT = Skill(
    nome="mood_vibe_scout",
    rotulo="Caça-vibe",
    resumo="Antes de haver foto: entrevista, shortlist de vibes e N referências de cada uma.",
    skill_md=".claude/skills/mood_vibe_scout/SKILL.md",
    params=(
        # Sem `gate`: a parada humana desta skill é fixa (aprovar a shortlist) e o `SKILL.md`
        # não declara flag para desligá-la. Inventar um `gate` aqui seria contrato falso.
        Param(
            nome="descricao",
            flag=None,
            posicional=True,
            tipo="texto",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Sobre a campanha",
                ajuda="o que você já sabe; é lido antes da entrevista e desativa as perguntas já respondidas",
                grupo="principal",
            ),
        ),
        Param(
            nome="vibes",
            flag="--vibes",
            tipo="lista",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Vibes garantidas",
                ajuda="slugs ou nomes separados por vírgula; entram sempre na shortlist",
                grupo="principal",
            ),
        ),
        Param(
            nome="n",
            flag="--n",
            tipo="inteiro",
            default=3,
            apresentacao=Apresentacao(
                rotulo="Imagens por vibe",
                # O SKILL.md NÃO declara máximo — declara um aviso acima de 8. Virar `max: 8`
                # seria inventar restrição que a skill não tem (risco 10 do recon da Wave 10).
                ajuda="acima de 8 a busca raspa o fundo da relevância: a skill avisa e segue se você confirmar",
                minimo=1,
            ),
        ),
        Param(
            nome="saida",
            flag="--saida",
            tipo="caminho",
            default="processo_manual/moodboard/fotos_vibe",
            apresentacao=Apresentacao(rotulo="Pasta de saída"),
        ),
        Param(
            nome="sem_entrevista",
            flag="--sem-entrevista",
            tipo="booleano",
            default=None,
            apresentacao=Apresentacao(
                rotulo="Pular a entrevista",
                ajuda="vai direto à shortlist com a descrição livre e as vibes garantidas",
            ),
        ),
    ),
)

SKILLS: tuple[Skill, ...] = (_ORQUESTRADOR, _BOARD_BUILDER, _VIBE_SCOUT)

# Skills `mood_` que existem em `.claude/skills/` e ficam FORA do manifesto, com o motivo.
# O teste de divergência confere que cada uma delas realmente não declara Invocação.
FORA_DO_MANIFESTO: dict[str, str] = {
    "mood_visual_dna": (
        "não tem seção de Invocação nem parâmetro de linha de comando — é invocada como "
        "subskill/subagente com a imagem e o objetivo"
    ),
}


def manifesto() -> dict[str, object]:
    """Devolve o manifesto serializável servido por `GET /api/skills/mood/params`.

    É construído a partir de constantes de módulo: não toca o disco, não lê os `SKILL.md` em
    tempo de requisição e portanto não tem modo de falha próprio. A conferência contra os
    `SKILL.md` é responsabilidade do teste de divergência, que roda no CI.
    """
    return {
        "versao": MANIFESTO_VERSAO,
        "skills": [s.to_dict() for s in SKILLS],
        "fora_do_manifesto": [{"nome": n, "motivo": m} for n, m in FORA_DO_MANIFESTO.items()],
    }


def skill(nome: str) -> Skill:
    """Devolve a skill do manifesto pelo nome.

    Raises:
        KeyError: quando `nome` não está no manifesto.
    """
    for s in SKILLS:
        if s.nome == nome:
            return s
    raise KeyError(nome)
