"""Painel das fotos de vibe pesquisadas no Pinterest — `[extensão]` (ADH-OS-20260902-03).

A skill `/mood_vibe_scout` coleta N referências por vibe e grava uma pasta com dezenas ou centenas
de `.jpg` mais um `_indice.json`. Este módulo é a "peneira": lista essas fotos paginadas, e copia
as escolhidas para uma pasta própria, de onde a cadeia `mood_orquestrador` parte.

Layout no disco (decisão D1 da wave 10 — FDD `docs/domains/mood/features/painel-vibes-fdd.md`):

    MOODBOARDS_DIR/_vibes/        saída do vibe_scout — SÓ LEITURA aqui
    MOODBOARDS_DIR/_escolhidas/   a peneira — `_escolhidas.json` + as cópias `<hash12>.<ext>`

As duas pastas vivem dentro de `MOODBOARDS_DIR` de propósito: ela já é servida pelo mount
`/mbfiles` (`studio/app.py:220`) e já é gitignored, então nada precisa mudar em `app.py` e nenhuma
imagem de terceiro entra no repositório. E `MBID_RE` (`service.py:32`) rejeita nomes iniciados por
`_`, logo estas pastas são invisíveis à biblioteca de mood boards — não viram board fantasma.

Regras que este módulo não negocia:
- **copiar, nunca mover** (D3): `_vibes/` é o resultado da pesquisa e não pode ser destruído;
- **deduplicação por hash do conteúdo** (D4): a mesma foto pode aparecer em duas vibes;
- **sem teto de escolhidas** (D5): o teto de 8 é do board (ADR-007) e não vale para a peneira;
- nenhum id vira `Path` antes de passar por regex (path traversal).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from ..common.atomic import project_lock, write_json_atomic
from ..common.ingest import MEDIA_EXT
from ..config import MOODBOARDS_DIR

#: Nomes das duas pastas. Começam com `_` para ficarem fora do `MBID_RE` da biblioteca.
VIBES_DIRNAME = "_vibes"
CHOSEN_DIRNAME = "_escolhidas"
#: Índice de metadados escrito pelo `mood_vibe_scout` (references/saida.md da skill).
INDEX_FILE = "_indice.json"
#: Índice reconstruível da peneira (a verdade são as cópias em disco).
CHOSEN_STATE_FILE = "_escolhidas.json"

#: Teto duro de itens por página (D2). Valor maior é CLAMPADO, não é erro.
MAX_PER_PAGE = 20
#: Teto de ids por chamada de `select_photos` — protege contra body absurdo, não é regra de negócio.
MAX_SELECT_IDS = 500
#: 12 hex de SHA-1, mesma convenção de `common/ingest.ingest_bytes`.
HASH_LEN = 12

IMG_EXT = MEDIA_EXT["image"]

#: Origem da foto, derivada do PREFIXO do arquivo (references/saida.md do `mood_vibe_scout`):
#: sem prefixo = veio do catálogo de 30 vibes; `custom-` = a pessoa pediu; `extra-` = a skill sugeriu.
ORIGENS: tuple[str, ...] = ("catalogo", "usuario", "sugestao")
PREFIX_ORIGEM: dict[str, str] = {"custom-": "usuario", "extra-": "sugestao"}

#: Id de uma foto de vibe É o nome do arquivo. A regex rejeita `/`, `..` e o `_` inicial — logo
#: `_indice.json` e `_folha-contato-N.jpg` nunca são listados nem selecionáveis.
VIBE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
#: Id de uma escolhida é o hash da cópia.
CHOSEN_ID_RE = re.compile(r"^[0-9a-f]{12}$")
#: `<prefixo><NN>-<slug>-<i>.<ext>` — de onde a vibe é lida quando o índice falta ou está corrompido.
FILENAME_RE = re.compile(r"^(?:custom-|extra-)?\d+-(?P<slug>.+)-\d+$")

#: Cache de hash por (caminho, mtime_ns, tamanho): `GET /api/vibes` marca `escolhida` lendo os
#: arquivos da página, e paginar para frente e para trás relê os mesmos 20 arquivos.
_hash_cache: dict[tuple[str, int, int], str] = {}
_HASH_CACHE_MAX = 4096


# ---------- caminhos ----------
def vibes_dir() -> Path:
    """Pasta de saída do `mood_vibe_scout`. Pode não existir — quem lê trata isso (E1)."""
    return MOODBOARDS_DIR / VIBES_DIRNAME


def chosen_dir() -> Path:
    """Pasta da peneira. Criada sob demanda, nunca no import (risco 7 do recon da wave 10)."""
    return MOODBOARDS_DIR / CHOSEN_DIRNAME


# ---------- índice do vibe_scout ----------
@dataclass(frozen=True, slots=True)
class IndexState:
    """Leitura do `_indice.json`, já degradada quando o arquivo falta ou está corrompido.

    `ok=False` NÃO é um valor de retorno ambíguo: `erro` diz exatamente o que houve e as fotos
    continuam listáveis pelo nome do arquivo. Levantar aqui deixaria o painel inteiro inútil por
    causa de um arquivo de metadados.
    """
    ok: bool
    erro: str | None
    campanha: str
    #: nome do arquivo -> {"vibe", "vibe_nome", "origem_url"}
    por_arquivo: dict[str, dict] = field(default_factory=dict)
    #: slugs das vibes na ordem em que o índice as declara (ordem da shortlist aprovada)
    ordem_vibes: list[str] = field(default_factory=list)
    #: slug -> nome legível
    nomes: dict[str, str] = field(default_factory=dict)


def read_index() -> IndexState:
    """Lê `_vibes/_indice.json` e indexa os metadados por nome de arquivo.

    Nunca levanta: ausência (E3) e corrupção (E4) viram `IndexState(ok=False, erro=...)`, porque
    as fotos existem no disco independentemente do índice.
    """
    arquivo = vibes_dir() / INDEX_FILE
    if not arquivo.is_file():
        return IndexState(ok=False, erro="ausente", campanha="")
    try:
        raw = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return IndexState(ok=False, erro=f"corrompido: {exc}", campanha="")
    if not isinstance(raw, dict) or not isinstance(raw.get("vibes"), list):
        return IndexState(ok=False, erro="corrompido: esperado um objeto com a lista `vibes`", campanha="")

    por_arquivo: dict[str, dict] = {}
    ordem: list[str] = []
    nomes: dict[str, str] = {}
    for entrada in raw["vibes"]:
        if not isinstance(entrada, dict):
            continue
        slug = str(entrada.get("slug") or "").strip()
        nome = str(entrada.get("nome") or slug).strip()
        if slug and slug not in nomes:
            nomes[slug] = nome or slug
            ordem.append(slug)
        for salva in entrada.get("salvas") or []:
            if not isinstance(salva, dict):
                continue
            nome_arquivo = Path(str(salva.get("arquivo") or "")).name
            if not nome_arquivo:
                continue
            url = salva.get("origem_url")
            por_arquivo[nome_arquivo] = {"vibe": slug, "vibe_nome": nome or slug,
                                         "origem_url": str(url) if url else None}
    return IndexState(ok=True, erro=None, campanha=str(raw.get("campanha") or ""),
                      por_arquivo=por_arquivo, ordem_vibes=ordem, nomes=nomes)


def _indice_public(indice: IndexState) -> dict:
    return {"ok": indice.ok, "erro": indice.erro, "campanha": indice.campanha}


# ---------- metadados derivados do nome do arquivo ----------
def origem_of(arquivo: str) -> str:
    """Origem da foto pelo prefixo do arquivo. O prefixo é a fonte de verdade porque sobrevive
    ao índice ausente ou corrompido."""
    for prefixo, origem in PREFIX_ORIGEM.items():
        if arquivo.startswith(prefixo):
            return origem
    return "catalogo"


def _slug_of(arquivo: str) -> str:
    """Slug da vibe pelo padrão `<prefixo><NN>-<slug>-<i>.<ext>`; `""` quando não bate."""
    achado = FILENAME_RE.match(Path(arquivo).stem)
    return achado.group("slug") if achado else ""


def _vibe_of(arquivo: str, indice: IndexState) -> str:
    meta = indice.por_arquivo.get(arquivo)
    return (meta or {}).get("vibe") or _slug_of(arquivo)


def file_hash(path: Path) -> str:
    """SHA-1 do conteúdo, 12 hex — a identidade de uma foto escolhida.

    Raises:
        OSError: arquivo ilegível (não é engolido: dedupe silenciosamente errado é pior).
    """
    stat = path.stat()
    chave = (str(path), stat.st_mtime_ns, stat.st_size)
    cacheado = _hash_cache.get(chave)
    if cacheado is not None:
        return cacheado
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:HASH_LEN]
    if len(_hash_cache) >= _HASH_CACHE_MAX:
        _hash_cache.clear()
    _hash_cache[chave] = digest
    return digest


# ---------- listagem das fotos de vibe ----------
def photo_files() -> list[Path]:
    """Imagens diretamente em `_vibes/`, em ordem estável de nome (a paginação depende disso).

    Ignora subpastas, arquivos iniciados por `_` (índice e folhas de contato) e o que não for
    imagem. Pasta inexistente devolve lista vazia (E1) — é o estado normal antes da primeira
    corrida do `mood_vibe_scout`.
    """
    pasta = vibes_dir()
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.iterdir()
                   if p.is_file() and p.suffix.lower() in IMG_EXT and VIBE_ID_RE.match(p.name)),
                  key=lambda p: p.name)


def _public_photo(path: Path, indice: IndexState, escolhidos: set[str]) -> dict:
    meta = indice.por_arquivo.get(path.name) or {}
    slug = meta.get("vibe") or _slug_of(path.name)
    return {
        "id": path.name,
        "arquivo": path.name,
        "url": f"/mbfiles/{VIBES_DIRNAME}/{quote(path.name)}",
        "vibe": slug,
        "vibe_nome": meta.get("vibe_nome") or indice.nomes.get(slug) or slug,
        "origem": origem_of(path.name),
        "origem_url": meta.get("origem_url"),
        "bytes": path.stat().st_size,
        "escolhida": file_hash(path) in escolhidos,
    }


def _check_paging(page: int, per_page: int) -> int:
    """Valida a paginação e devolve o `per_page` já clampado.

    Raises:
        ValueError: `page` ou `per_page` menores que 1.
    """
    if page < 1:
        raise ValueError("page deve ser >= 1")
    if per_page < 1:
        raise ValueError("per_page deve ser >= 1")
    return min(per_page, MAX_PER_PAGE)


def list_vibes(*, page: int = 1, per_page: int = MAX_PER_PAGE,
               vibe: str | None = None, origem: str | None = None) -> dict:
    """Página de fotos de vibe, filtrável por vibe e por origem.

    Página além do fim devolve `items` vazio com `total`/`pages` corretos (E8) — o front usa isso
    para oferecer a volta à última página. `escolhida` é resolvido por hash SÓ para os itens da
    página, para não ler a pasta inteira a cada request.

    Raises:
        ValueError: paginação inválida (E5/E7) ou `origem` fora de `ORIGENS` (E9).
    """
    per_page = _check_paging(page, per_page)
    if origem is not None and origem not in ORIGENS:
        raise ValueError(f"origem inválida: {origem!r} (aceitas: {', '.join(ORIGENS)})")

    indice = read_index()
    paths = photo_files()
    if vibe:
        paths = [p for p in paths if _vibe_of(p.name, indice) == vibe]
    if origem:
        paths = [p for p in paths if origem_of(p.name) == origem]

    total = len(paths)
    pages = max(1, -(-total // per_page))
    inicio = (page - 1) * per_page
    escolhidos = chosen_hashes()
    items = [_public_photo(p, indice, escolhidos) for p in paths[inicio:inicio + per_page]]
    return {"items": items, "page": page, "per_page": per_page, "total": total, "pages": pages,
            "indice": _indice_public(indice), "pasta": str(vibes_dir())}


def facets() -> dict:
    """Vibes e origens disponíveis com contagem — o que alimenta os filtros da tela.

    A ordem das vibes segue a ordem do `_indice.json` (a shortlist aprovada pelo usuário); as que
    não estão no índice vão para o fim, em ordem alfabética.
    """
    indice = read_index()
    paths = photo_files()
    por_vibe: dict[str, dict] = {}
    por_origem: dict[str, int] = dict.fromkeys(ORIGENS, 0)
    for path in paths:
        slug = _vibe_of(path.name, indice)
        origem = origem_of(path.name)
        por_origem[origem] += 1
        entrada = por_vibe.setdefault(slug, {"slug": slug, "nome": indice.nomes.get(slug) or slug,
                                             "origem": origem, "total": 0})
        entrada["total"] += 1
    ordem = {slug: i for i, slug in enumerate(indice.ordem_vibes)}
    vibes = sorted(por_vibe.values(), key=lambda v: (ordem.get(v["slug"], len(ordem)), v["slug"]))
    return {"vibes": vibes,
            "origens": [{"origem": o, "total": por_origem[o]} for o in ORIGENS if por_origem[o]],
            "total": len(paths), "escolhidas": count_chosen(),
            "indice": _indice_public(indice), "pasta": str(vibes_dir())}


# ---------- a peneira (`_escolhidas/`) ----------
def read_chosen() -> list[dict]:
    """Estado da peneira, na ordem em que as fotos foram escolhidas.

    Estado ausente ou corrompido é tratado como vazio (E16): `_escolhidas.json` é um índice
    reconstruível, não a verdade — a verdade são as cópias em disco. Entradas sem id válido são
    descartadas para nenhum id inventado virar caminho de arquivo.
    """
    arquivo = chosen_dir() / CHOSEN_STATE_FILE
    if not arquivo.is_file():
        return []
    try:
        raw = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    itens = raw.get("itens") if isinstance(raw, dict) else None
    if not isinstance(itens, list):
        return []
    return [i for i in itens
            if isinstance(i, dict) and CHOSEN_ID_RE.match(str(i.get("id") or ""))]


def _write_chosen(itens: list[dict]) -> None:
    write_json_atomic(chosen_dir() / CHOSEN_STATE_FILE, {"versao": 1, "itens": itens},
                      ensure_ascii=False, indent=1, newline=True)


def chosen_hashes() -> set[str]:
    """Hashes já na peneira — é por eles que a deduplicação acontece (D4)."""
    return {str(i["id"]) for i in read_chosen()}


def count_chosen() -> int:
    """Quantas fotos estão na peneira. É o contador que a feature 01 consome (seção 12 do FDD)."""
    return len(read_chosen())


def _public_chosen(item: dict) -> dict:
    arquivo = str(item.get("arquivo") or "")
    return {**item,
            "url": f"/mbfiles/{CHOSEN_DIRNAME}/{quote(arquivo)}",
            "caminho": str(chosen_dir() / arquivo)}


def list_chosen(*, page: int = 1, per_page: int = MAX_PER_PAGE) -> dict:
    """Página da peneira. `caminho` de cada item é o caminho absoluto que a feature 01 passa
    em `--foto` para o `/mood_orquestrador`.

    Raises:
        ValueError: paginação inválida (E5/E7).
    """
    per_page = _check_paging(page, per_page)
    itens = read_chosen()
    total = len(itens)
    pages = max(1, -(-total // per_page))
    inicio = (page - 1) * per_page
    return {"items": [_public_chosen(i) for i in itens[inicio:inicio + per_page]],
            "page": page, "per_page": per_page, "total": total, "pages": pages,
            "pasta": str(chosen_dir())}


def select_photos(ids: Sequence[str]) -> dict:
    """Copia as fotos indicadas de `_vibes/` para `_escolhidas/`, deduplicando por hash.

    Copia, **nunca move** (D3), e não tem teto (D5). Ids repetidos na mesma chamada são
    processados uma vez. O resultado separa o que entrou (`copiadas`), o que já estava
    (`duplicadas`, E13) e o que sumiu do disco entre a listagem e o salvamento (`ausentes`, E12) —
    nunca um número solto.

    Raises:
        ValueError: lista vazia, acima de `MAX_SELECT_IDS`, ou id que não é nome de arquivo de
            imagem válido (E10/E11) — o request inteiro é rejeitado e nada é copiado.
        OSError: falha de I/O na cópia (E17). Propaga: cópia que não aconteceu não pode virar
            sucesso silencioso.
    """
    if not ids:
        raise ValueError("informe ao menos um id")
    if len(ids) > MAX_SELECT_IDS:
        raise ValueError(f"no máximo {MAX_SELECT_IDS} ids por chamada")
    for photo_id in ids:
        if not VIBE_ID_RE.match(photo_id or "") or Path(photo_id).suffix.lower() not in IMG_EXT:
            raise ValueError(f"id inválido: {photo_id!r}")

    origem_pasta = vibes_dir()
    destino_pasta = chosen_dir()
    indice = read_index()
    copiadas: list[str] = []
    duplicadas: list[str] = []
    ausentes: list[str] = []

    with project_lock(destino_pasta):
        itens = read_chosen()
        conhecidos = {str(i["id"]) for i in itens}
        for photo_id in dict.fromkeys(ids):     # preserva a ordem e não processa o mesmo id 2x
            origem_arquivo = origem_pasta / photo_id
            if not origem_arquivo.is_file():
                ausentes.append(photo_id)
                continue
            digest = file_hash(origem_arquivo)
            if digest in conhecidos:
                duplicadas.append(photo_id)
                continue
            destino_pasta.mkdir(parents=True, exist_ok=True)
            destino_arquivo = destino_pasta / f"{digest}{origem_arquivo.suffix.lower()}"
            shutil.copy2(origem_arquivo, destino_arquivo)
            meta = indice.por_arquivo.get(photo_id) or {}
            slug = meta.get("vibe") or _slug_of(photo_id)
            itens.append({
                "id": digest,
                "arquivo": destino_arquivo.name,
                "origem_arquivo": photo_id,
                "vibe": slug,
                "vibe_nome": meta.get("vibe_nome") or indice.nomes.get(slug) or slug,
                "origem": origem_of(photo_id),
                "origem_url": meta.get("origem_url"),
                "bytes": destino_arquivo.stat().st_size,
                "escolhida_em": datetime.now().isoformat(timespec="seconds"),
            })
            conhecidos.add(digest)
            copiadas.append(photo_id)
        _write_chosen(itens)
        total = len(itens)

    return {"copiadas": copiadas, "duplicadas": duplicadas, "ausentes": ausentes,
            "total_escolhidas": total}


def remove_chosen(chosen_id: str) -> dict:
    """Tira uma foto da peneira: apaga a CÓPIA e a entrada de estado.

    O original em `_vibes/` não é tocado — é o outro lado da decisão "copiar, nunca mover".

    Raises:
        ValueError: id fora de `CHOSEN_ID_RE` (E14).
        KeyError: id que não está na peneira (E15). O router traduz para 404 com mensagem
            própria: o handler global de KeyError fala de "projeto", que aqui seria mentira.
    """
    if not CHOSEN_ID_RE.match(chosen_id or ""):
        raise ValueError(f"id inválido: {chosen_id!r}")
    with project_lock(chosen_dir()):
        itens = read_chosen()
        alvo = next((i for i in itens if str(i["id"]) == chosen_id), None)
        if alvo is None:
            raise KeyError(chosen_id)
        restantes = [i for i in itens if str(i["id"]) != chosen_id]
        arquivo = str(alvo.get("arquivo") or "")
        if arquivo and Path(arquivo).name == arquivo:   # nunca sair de `_escolhidas/`
            (chosen_dir() / arquivo).unlink(missing_ok=True)
        _write_chosen(restantes)
        total = len(restantes)
    return {"removida": chosen_id, "total_escolhidas": total}
