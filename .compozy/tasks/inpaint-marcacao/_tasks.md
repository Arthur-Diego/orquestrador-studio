---
schema_version: "compozy.tasks/v2"
workflow: inpaint-marcacao
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
  edges:
    - from: task_01
      to: task_02
---

# Inpaint por marcação (`edit_area`) — Task List

Feature `[extensão]` da Wave 9, sub-wave 1. TechSpec normativa: `_techspec.md`
(cópia do FDD aprovado em `docs/domains/storyboard/features/inpaint-marcacao-fdd.md`).

| Task | Título | Tipo | Complexidade | Critérios do FDD §9 |
|---|---|---|---|---|
| task_01 | Backend: persistência da marcação, kind `edit_area` e ação de custo | backend | high | 1, 2, 3, 4, 5, 6 |
| task_02 | Frontend: canvas `annotate.js` e painel "Área marcada" na etapa 4 | frontend | medium | 7 |

Critério 8 do FDD (`make verify` verde, núcleo sem diff, testes sem rede/navegador) é
transversal e vale para as duas tasks.

## Fatiamento

O corte é de domínio (backend Python × frontend estático sem build), não de arquivo:
o backend inteiro (serviço + settings + rota) é uma fatia vertical só, porque a rota
`POST .../annotate` não tem sentido sem `import_annotation` e o `annotation_id` do
`GenerateReq` não tem sentido sem o kind `edit_area`. O frontend depende do contrato HTTP
já existir para chamar `/annotate`, `/cost` e `/generate`.

Artefatos de fechamento fora do pipeline (feitos pela frente do `dd-parallel`, não por
estas tasks): diagrama Mermaid, nota aditiva no `storyboard-fdd.md` (já commitados) e a
coleção Postman (gerada pelo agente `dd-parallel-postman` depois do backend pronto).
