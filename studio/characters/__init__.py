"""`[extensão]` Biblioteca global de Personagens e identidade visual (ADR-039).

Área independente de campanha (padrão ADR-013, como a biblioteca de mood boards): explorar um
personagem no motor local (grátis), **fixar** o escolhido, gerar o descritor canônico de
identidade (via `prompter`, papel `character`) e um character sheet, e **aplicar** o personagem a
uma campanha — a partir daí o descritor reancora os prompts das etapas 3–5 (o chat o injeta).

Não substitui nada do curso; é extensão marcada `[extensão]`. Armazenamento em `STUDIO_CHARACTERS`
(default `<repo>/characters/`, gitignored), fora de `projects/` (ADR-003). Geração local via a
ponte `studio/localengine.py` (ADR-033), grátis; identidade paga (Soul ID) via a ponte
`studio/higgsfield.py` (ADR-002).
"""
