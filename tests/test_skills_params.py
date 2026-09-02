"""Teste de divergência: manifesto (`studio/moodboards/skills_params.py`) × `SKILL.md` reais.

É o que impede as duas verdades de se separarem em silêncio. Ele lê os arquivos versionados em
`.claude/skills/mood_*/SKILL.md`, extrai deles a **camada declarada** de cada parâmetro e compara
com o manifesto, nas duas direções.

## O que ele cobra (camada declarada)

1. toda skill `mood_*` com seção `## Invocação` está no manifesto — e as que não estão têm
   motivo registrado em `FORA_DO_MANIFESTO` **e** de fato não declaram Invocação;
2. o conjunto de flags é idêntico nos dois lados — flag nova na skill quebra; flag do manifesto
   que sumiu da skill quebra; flag omitida de propósito só passa se estiver em
   `parametros_ignorados`, com motivo;
3. o `default` do manifesto é literalmente o default declarado no `SKILL.md` (e `None` quando o
   `SKILL.md` não declara nenhum);
4. as `opcoes` dos enums são exatamente os literais que o `SKILL.md` lista (mais o `agregador`,
   quando há — `todos` no `--objetivo` do orquestrador);
5. o argumento posicional existe no manifesto se, e somente se, existir no bloco de uso.

## O que ele NÃO cobra (camada de apresentação) — e por quê

`rotulo`, `ajuda`, `grupo`, `min`, `max` e `obrigatorio_em_auto` são decisão de UI. **Nenhum
`SKILL.md` declara essas chaves.** Compará-las obrigaria a inventar declarações nas skills ou a
afrouxar a comparação inteira até ela não pegar mais nada — o teste viraria decoração. Dois
exemplos concretos do risco: o plano propunha `max: 8` para o `--n` da `mood_vibe_scout` (o
`SKILL.md` declara um *aviso* acima de 8, não um teto) e `min: 4` para `--board` (o `SKILL.md`
diz "inteiro ≥ 4" em prosa livre, não em chave declarada).

## Guarda anti-teatro

Se o formato dos `SKILL.md` mudar e o parser passar a devolver conjuntos vazios, todas as
comparações acima passariam trivialmente. Por isso `test_o_parser_realmente_extrai_o_conteudo`
ancora valores literais lidos à mão dos `SKILL.md` — se ele falhar, é o parser que quebrou, não
o manifesto.

Sem `skipif`: os `SKILL.md` são versionados no repositório, então a ausência de um arquivo é
falha legítima e não motivo para pular o teste.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from studio.moodboards import skills_params as sp

RAIZ = Path(__file__).resolve().parents[1]
DIR_SKILLS = RAIZ / ".claude" / "skills"

# `--flag`, mas não o `---` dos separadores de tabela markdown.
RE_FLAG = re.compile(r"--([a-z][a-z0-9-]*)")
# `--gate interativo|auto` no bloco de uso. Só minúsculas: `LISTA|todos` e `ARQUIVO|TRECHO` são
# metavariáveis do bloco de uso, não literais aceitos.
RE_OPCOES_USO = re.compile(r"--([a-z][a-z0-9-]*)\s+([a-zà-ú][a-zà-ú0-9-]*(?:\|[a-zà-ú][a-zà-ú0-9-]*)+)")
# Token literal entre crases: `ambiente`. Exclui caminhos (`processo_manual/…`), placeholders
# (`<saida>/…`) e nomes de skill (`mood_visual_dna`), que não são valores de enum.
RE_TOKEN = re.compile(r"`([a-zà-ú][a-zà-ú0-9-]*)`")
# `/mood_orquestrador [ARQUIVO|…]` — o primeiro colchete da linha de uso, se não for uma flag.
RE_POSICIONAL = re.compile(r"^/\S+\s+\[([^\]]+)\]")

# Células da coluna "Default" que significam "a skill pergunta / não há default declarado".
SEM_DEFAULT = {"—", "-", "–", ""}


# --------------------------------------------------------------------------- parser do SKILL.md
def _texto(nome_skill: str) -> str:
    caminho = DIR_SKILLS / nome_skill / "SKILL.md"
    assert caminho.is_file(), f"{caminho} não existe — as skills mood_ precisam estar versionadas"
    return caminho.read_text(encoding="utf-8")


def secao_invocacao(texto: str) -> str:
    """Devolve o corpo da seção `## Invocação` (até o próximo `## `), ou string vazia."""
    linhas = texto.splitlines()
    inicio = next((i for i, ln in enumerate(linhas) if ln.strip() == "## Invocação"), None)
    if inicio is None:
        return ""
    fim = len(linhas)
    for i in range(inicio + 1, len(linhas)):
        if linhas[i].startswith("## "):
            fim = i
            break
    return "\n".join(linhas[inicio + 1 : fim])


def bloco_uso(secao: str) -> str:
    """Devolve o primeiro bloco de código cercado por ``` da seção de Invocação."""
    linhas = secao.splitlines()
    abre = next((i for i, ln in enumerate(linhas) if ln.strip().startswith("```")), None)
    if abre is None:
        return ""
    for i in range(abre + 1, len(linhas)):
        if linhas[i].strip().startswith("```"):
            return "\n".join(linhas[abre + 1 : i])
    return ""


def flags_declaradas(secao: str) -> set[str]:
    """Todas as flags citadas na seção de Invocação (bloco de uso, tabela e prosa)."""
    return {f"--{nome}" for nome in RE_FLAG.findall(secao)}


def tem_posicional(secao: str) -> bool:
    """Diz se a linha de uso abre com um argumento posicional (colchete que não é flag)."""
    primeira = next((ln.strip() for ln in bloco_uso(secao).splitlines() if ln.strip()), "")
    achado = RE_POSICIONAL.search(primeira)
    return bool(achado) and not achado.group(1).startswith("--")


def _indice_coluna(secao: str, titulo: str) -> int | None:
    """Índice da coluna `titulo` no cabeçalho da primeira tabela markdown da seção."""
    for linha in secao.splitlines():
        s = linha.strip()
        if not s.startswith("|"):
            continue
        celulas = [c.strip().lower() for c in s.strip("|").split("|")]
        if titulo.lower() in celulas:
            return celulas.index(titulo.lower())
    return None


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def declaracao(secao: str, flag: str) -> str | None:
    """Devolve a declaração da flag: a linha da tabela, ou o item de lista com suas continuações.

    Casa tanto `| posicional ou \\`--foto\\` | … |` quanto `- \\`--gate\\`: …`.
    """
    alvo = f"`{flag}`"
    linhas = secao.splitlines()
    for i, linha in enumerate(linhas):
        s = linha.strip()
        if s.startswith("|") and alvo in _celulas(linha)[0]:
            return linha
        if s.startswith("- ") and s[2:].startswith(alvo):
            # Item de lista pode continuar nas linhas indentadas seguintes.
            partes = [s]
            for seguinte in linhas[i + 1 :]:
                if not seguinte.strip() or not seguinte.startswith((" ", "\t")):
                    break
                partes.append(seguinte.strip())
            return " ".join(partes)
    return None


def default_declarado(secao: str, flag: str) -> str | None:
    """Extrai o default literal declarado para a flag, ou `None` se o `SKILL.md` não declara.

    Reconhece as três formas usadas pelas skills `mood_`: a coluna "Default" da tabela do
    orquestrador, o `**Default 3.**` / ``Default `caminho` `` em prosa da `mood_vibe_scout`, e o
    ``` `interativo` (default) ``` da `mood_board_builder`.
    """
    linha = declaracao(secao, flag)
    if linha is None:
        return None
    if linha.strip().startswith("|"):
        idx = _indice_coluna(secao, "Default")
        celulas = _celulas(linha)
        bruto = celulas[idx] if idx is not None and idx < len(celulas) else ""
        if bruto in SEM_DEFAULT or bruto.lower().startswith("pergunta"):
            return None
        return bruto.strip("`")
    for padrao in (r"\*\*Default\s+([^*]+?)\.?\*\*", r"[Dd]efault\s+`([^`]+)`", r"`([^`]+)`\s+\(default\)"):
        achado = re.search(padrao, linha)
        if achado:
            return achado.group(1).strip().strip("`")
    return None


def opcoes_declaradas(secao: str, flag: str) -> set[str]:
    """União dos literais aceitos pela flag: os do bloco de uso e os da linha de declaração."""
    achados = {f"--{nome}": set(valores.split("|")) for nome, valores in RE_OPCOES_USO.findall(bloco_uso(secao))}
    opcoes = achados.get(flag, set())
    linha = declaracao(secao, flag)
    if linha is None:
        return opcoes
    if linha.strip().startswith("|"):
        idx = _indice_coluna(secao, "Valores aceitos")
        celulas = _celulas(linha)
        alvo = celulas[idx] if idx is not None and idx < len(celulas) else ""
    else:
        alvo = linha.split(":", 1)[1] if ":" in linha else linha
    return opcoes | set(RE_TOKEN.findall(alvo))


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def secoes() -> dict[str, str]:
    """Seção de Invocação de cada skill do manifesto, indexada pelo nome da skill."""
    return {s.nome: secao_invocacao(_texto(s.nome)) for s in sp.SKILLS}


PARAMS_COM_FLAG = [
    pytest.param(s.nome, p, id=f"{s.nome}{p.flag}") for s in sp.SKILLS for p in s.params if p.flag
]
PARAMS_ENUM = [
    pytest.param(s.nome, p, id=f"{s.nome}{p.flag}")
    for s in sp.SKILLS
    for p in s.params
    if p.flag and p.tipo in ("enum", "multi")
]


# --------------------------------------------------------------------------- guarda anti-teatro
def test_o_parser_realmente_extrai_o_conteudo_dos_skill_md(secoes):
    """Âncoras literais conferidas à mão nos `SKILL.md`. Se isto falha, o parser quebrou."""
    orq, builder, scout = secoes["mood_orquestrador"], secoes["mood_board_builder"], secoes["mood_vibe_scout"]

    assert orq and builder and scout, "seção `## Invocação` não encontrada em alguma skill"
    assert "--gate" in flags_declaradas(orq)
    assert len(flags_declaradas(orq)) >= 7
    assert len(flags_declaradas(builder)) >= 8
    assert len(flags_declaradas(scout)) >= 4

    # Um default por forma sintática — tabela, prosa em negrito e "(default)".
    assert default_declarado(orq, "--board") == "8"
    assert default_declarado(scout, "--n") == "3"
    assert default_declarado(builder, "--gate") == "interativo"
    # E a ausência de default também é lida como ausência, não como erro do parser.
    assert default_declarado(orq, "--params") is None
    assert default_declarado(builder, "--board") is None

    assert opcoes_declaradas(orq, "--gate") == {"interativo", "auto"}
    assert opcoes_declaradas(orq, "--objetivo") == {"ambiente", "campanha", "produto", "personagem", "todos"}
    assert tem_posicional(orq) and tem_posicional(scout) and not tem_posicional(builder)


# --------------------------------------------------------------------------- cobertura de skills
def test_toda_skill_mood_com_invocacao_esta_no_manifesto():
    diretorios = sorted(p.name for p in DIR_SKILLS.glob("mood_*") if p.is_dir())
    assert diretorios, f"nenhuma skill mood_ encontrada em {DIR_SKILLS}"

    no_manifesto = {s.nome for s in sp.SKILLS}
    for nome in diretorios:
        tem_invocacao = bool(secao_invocacao(_texto(nome)))
        if nome in no_manifesto:
            assert tem_invocacao, f"{nome} está no manifesto mas não declara `## Invocação`"
            continue
        assert nome in sp.FORA_DO_MANIFESTO, (
            f"{nome} não está no manifesto nem em FORA_DO_MANIFESTO — se ela ganhou parâmetros, "
            "exponha-os; se não, registre o motivo da exclusão"
        )
        assert not tem_invocacao, (
            f"{nome} está em FORA_DO_MANIFESTO porque não tinha parâmetros, mas agora declara "
            "`## Invocação` — o manifesto precisa expô-la"
        )


def test_todo_skill_md_do_manifesto_existe_no_caminho_declarado():
    for s in sp.SKILLS:
        caminho = RAIZ / s.skill_md
        assert caminho.is_file(), f"{s.nome}: skill_md aponta para {s.skill_md}, que não existe"
        assert caminho == DIR_SKILLS / s.nome / "SKILL.md"


# --------------------------------------------------------------------------- divergência de flags
@pytest.mark.parametrize("nome_skill", [s.nome for s in sp.SKILLS])
def test_as_flags_do_manifesto_e_do_skill_md_sao_as_mesmas(nome_skill, secoes):
    skill = sp.skill(nome_skill)
    na_skill = flags_declaradas(secoes[nome_skill])
    no_manifesto = {p.flag for p in skill.params if p.flag}
    ignoradas = {i.flag for i in skill.ignorados}

    inventadas = no_manifesto - na_skill
    assert not inventadas, f"{nome_skill}: o manifesto expõe flags que o SKILL.md não declara: {sorted(inventadas)}"

    faltando = na_skill - no_manifesto - ignoradas
    assert not faltando, (
        f"{nome_skill}: o SKILL.md declara flags que o manifesto não expõe: {sorted(faltando)} — "
        "exponha-as ou registre-as em `ignorados`, com motivo"
    )

    orfas = ignoradas - na_skill
    assert not orfas, f"{nome_skill}: `ignorados` cita flags que o SKILL.md não declara mais: {sorted(orfas)}"


def test_toda_flag_ignorada_tem_motivo():
    for s in sp.SKILLS:
        for ignorada in s.ignorados:
            assert ignorada.motivo.strip(), f"{s.nome}{ignorada.flag}: ignorada sem motivo"


# --------------------------------------------------------------------------- divergência de default
@pytest.mark.parametrize(("nome_skill", "param"), PARAMS_COM_FLAG)
def test_o_default_do_manifesto_e_o_declarado_no_skill_md(nome_skill, param, secoes):
    esperado = default_declarado(secoes[nome_skill], param.flag)
    obtido = None if param.default is None else str(param.default)
    assert obtido == esperado, (
        f"{nome_skill}{param.flag}: manifesto diz default={obtido!r}, SKILL.md declara {esperado!r}"
    )


# --------------------------------------------------------------------------- divergência de enum
@pytest.mark.parametrize(("nome_skill", "param"), PARAMS_ENUM)
def test_as_opcoes_do_enum_sao_as_declaradas_no_skill_md(nome_skill, param, secoes):
    esperado = opcoes_declaradas(secoes[nome_skill], param.flag)
    obtido = set(param.opcoes) | ({param.agregador} if param.agregador else set())
    assert obtido == esperado, (
        f"{nome_skill}{param.flag}: manifesto expõe {sorted(obtido)}, SKILL.md declara {sorted(esperado)}"
    )


@pytest.mark.parametrize("nome_skill", [s.nome for s in sp.SKILLS])
def test_toda_flag_com_alternativas_no_bloco_de_uso_e_enum_no_manifesto(nome_skill, secoes):
    """`--gate interativo|auto` no bloco de uso obriga o manifesto a tratar a flag como enum."""
    skill = sp.skill(nome_skill)
    por_flag = {p.flag: p for p in skill.params if p.flag}
    for nome_flag, valores in RE_OPCOES_USO.findall(bloco_uso(secoes[nome_skill])):
        flag = f"--{nome_flag}"
        param = por_flag.get(flag)
        assert param is not None, f"{nome_skill}: {flag} tem alternativas no bloco de uso e não está no manifesto"
        assert param.tipo in ("enum", "multi"), f"{nome_skill}{flag}: alternativas no bloco de uso, mas tipo={param.tipo}"
        assert set(valores.split("|")) <= set(param.opcoes)


# --------------------------------------------------------------------------- posicional
@pytest.mark.parametrize("nome_skill", [s.nome for s in sp.SKILLS])
def test_o_posicional_do_manifesto_bate_com_o_bloco_de_uso(nome_skill, secoes):
    posicionais = [p.nome for p in sp.skill(nome_skill).params if p.posicional]
    if tem_posicional(secoes[nome_skill]):
        assert len(posicionais) == 1, (
            f"{nome_skill}: o bloco de uso abre com um argumento posicional; o manifesto declara "
            f"{posicionais or 'nenhum'}"
        )
    else:
        assert not posicionais, f"{nome_skill}: manifesto declara posicional {posicionais}, o bloco de uso não tem"


# --------------------------------------------------------------------------- coerência interna
@pytest.mark.parametrize(("nome_skill", "param"), [(s.nome, p) for s in sp.SKILLS for p in s.params])
def test_cada_param_e_alcancavel_por_flag_ou_por_posicao(nome_skill, param):
    assert param.flag or param.posicional, f"{nome_skill}.{param.nome}: sem flag e sem posição — inalcançável"
    assert (param.tipo in ("enum", "multi")) == bool(param.opcoes), (
        f"{nome_skill}.{param.nome}: tipo={param.tipo} e opcoes={param.opcoes} são incoerentes"
    )
    if param.agregador:
        assert param.tipo == "multi", f"{nome_skill}.{param.nome}: agregador só faz sentido em tipo multi"
    assert param.apresentacao.rotulo.strip(), f"{nome_skill}.{param.nome}: sem rótulo"


def test_nomes_de_param_sao_unicos_por_skill():
    for s in sp.SKILLS:
        nomes = [p.nome for p in s.params]
        assert len(nomes) == len(set(nomes)), f"{s.nome}: nomes de parâmetro repetidos em {nomes}"


def test_a_vibe_scout_nao_ganha_um_gate_inventado(secoes):
    """Regressão do risco 10 do recon: a parada humana do scout é fixa, não há flag para ela."""
    assert "--gate" not in flags_declaradas(secoes["mood_vibe_scout"])
    assert not [p for p in sp.skill("mood_vibe_scout").params if p.nome == "gate"]


def test_o_teto_do_n_da_vibe_scout_nao_e_inventado():
    """O `SKILL.md` declara um aviso acima de 8, não um máximo — `max` fica `None`."""
    n = next(p for p in sp.skill("mood_vibe_scout").params if p.nome == "n")
    assert n.apresentacao.maximo is None
    assert "8" in n.apresentacao.ajuda
