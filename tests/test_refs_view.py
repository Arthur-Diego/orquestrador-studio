"""Backend da etapa 1 e fidelidades da aula 009 que NÃO dependem da tela.

Wave 10 · E5 (card [REACT-06]): a tela migrou para React (`studio/etapas/refs/ui/index.tsx`) e os
antigos asserts sobre `refs/view.{html,js}` viraram substituto Vitest em
`studio/etapas/refs/ui/index.test.tsx` (recon §7.2). O que sobra aqui é backend puro — os endpoints
da marca validada (ADR-020) e as fidelidades à aula 009 que vivem no `guide.py` (ADR-004: o texto de
aula não se perde; a tela é que deixou de desenhá-lo).
"""


def _guide(client):
    pid = client.post("/api/projects", json={"name": "Refs View", "product": "energy drink"}).json()["id"]
    r = client.get(f"/api/projects/{pid}/guide/refs")
    assert r.status_code == 200, r.text
    return r.json()


def test_guide_keeps_the_lesson_texts_the_screen_no_longer_draws(client):
    """ADR-004: as regras de origem (direitos autorais) e a segunda fonte da aula (Explore do
    Midjourney) seguem no guia mesmo com o lede encurtado e o painel de upload fora da tela."""
    what = _guide(client)["what"]
    assert "regra do Studio, não da aula" in what
    assert "Explore do Midjourney" in what


def test_validated_brand_endpoints_persist_and_drive_suggestions(client):
    """ADR-020 `[extensão]`: GET/PUT da marca validada e `/api/suggest-terms?pid=` só dela."""
    pid = client.post("/api/projects", json={"name": "Brand API", "product": "energy drink",
                                             "vibe": "snow neon"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/refs/validated-brand").json() == {"brand": ""}

    r = client.put(f"/api/projects/{pid}/refs/validated-brand", json={"brand": " Red Bull "})
    assert r.status_code == 200 and r.json() == {"brand": "Red Bull"}
    assert client.get(f"/api/projects/{pid}/refs/validated-brand").json() == {"brand": "Red Bull"}

    # com pid de projeto com marca validada, o suggest sai só dela (ignora product/vibe/brand)
    terms = client.get(f"/api/suggest-terms?product=energy+drink&vibe=snow+neon&pid={pid}").json()
    assert len(terms) >= 12 and all(t.startswith("Red Bull ") for t in terms)
    assert not any("energy drink" in t for t in terms)

    # sem pid (ou projeto sem marca validada) mantém o comportamento atual (product/vibe/brand)
    mixed = client.get("/api/suggest-terms?product=energy+drink&vibe=snow+neon").json()
    assert "energy drink ad campaign" in mixed


def test_validated_brand_endpoints_reject_unknown_project(client):
    assert client.get("/api/projects/nao-existe/refs/validated-brand").status_code == 404
    assert client.put("/api/projects/nao-existe/refs/validated-brand", json={"brand": "x"}).status_code == 404
