### HLD: characters (biblioteca de Personagens e identidade) `[extensão]`

Versão: 1.0 (Onda D — explorar/fixar/sheet/aplicar + Soul ID + nota de identidade)
Data: 2026-09-05
Task-Id: ADH-OS-20260905-07
Responsável: Arthur Diego (modo autônomo /dd-parallel, aprovação total)

---

### Objetivo técnico
Permitir **acertar um personagem e manter a identidade visual** entre as cenas de uma campanha, em
foto e vídeo. Área global independente de campanha (padrão ADR-013), com geração de exploração no
**motor local grátis** (ADR-033) e identidade paga opcional via **Soul ID** da Higgsfield
(ADR-002). É `[extensão]` (ADR-039): o curso não ensina character sheet nem consistência.

### Componentes
| Componente | Papel |
| --- | --- |
| `studio/characters/service.py` | Estado em arquivo (ADR-003) sob `STUDIO_CHARACTERS`: CRUD, refs, `explore` (job local), `lock` (+descritor), `sheet` (job local), `apply_to_project`/`applied`, `score` (gate opcional), Soul (`soul_images`/`attach_soul`). |
| `studio/characters/router.py` | Rotas da área global + binding por campanha. CharacterError→422; KeyError→404; CliUnavailable→409. |
| `studio/common/prompter.py` | Papel novo `character`: escreve o descritor canônico de identidade a partir da(s) referência(s). |
| `studio/higgsfield.py` | `soul_create`/`soul_list` (Soul ID via CLI oficial, ADR-002). |
| `studio/mcp/actions.py` | Tools `character_*` + injeção do descritor nos prompts de base/storyboard. |
| `frontend/src/areas/characters/CharactersArea.tsx` | Área do shell: lista, criar, explorar, fixar, sheet, aplicar. |

### Fluxo
1. **Criar** personagem (nome, estilo foto/anime/3d).
2. **Explorar** (`explore`): N variações no motor local (grátis, seeds fixas) → candidatos.
3. **Fixar** (`lock`): o usuário escolhe a que acertou (`ui.choose_images`); o Studio grava
   `locked_ref` e gera o **descritor canônico** (prompter, papel `character`).
4. **Character sheet** (`sheet`): vistas (frente/3-4/perfil/corpo) ancoradas no descritor, local.
5. **Aplicar** (`apply_to_project`): grava `project.json.character = {id, name, descriptor, style}`.
6. **Injeção**: o chat lê o personagem aplicado e prepend o descritor aos prompts de **base** e
   **storyboard** (não no mood — vibe sem pessoas). A identidade viaja pelo campo de instrução das
   rotas existentes; nenhuma etapa é modificada.
7. **Identidade paga**: `character_bind_soul` treina um Soul (confirmação antes; plano Basic+).
8. **Nota de identidade** (`score`): `engine faces compare` (local, opcional); degrada se ausente.

### Interfaces
| Rota | Nota |
| --- | --- |
| `GET|POST /api/characters` | listar / criar |
| `GET|PATCH|DELETE /api/characters/{cid}` | detalhe / editar / remover |
| `POST /api/characters/{cid}/refs/upload` | refs do usuário |
| `POST /api/characters/{cid}/explore` · `GET .../candidates` · `GET .../job` | exploração local (grátis) |
| `POST /api/characters/{cid}/lock` · `POST .../sheet` | fixar (+descritor) · character sheet |
| `GET|POST /api/characters/{cid}/soul` | Soul ID (pago, ADR-002) |
| `POST /api/characters/{cid}/score` | nota de identidade (opcional, local) |
| `GET|POST|DELETE /api/projects/{pid}/character` | binding por campanha |
| `/cfiles/*` | estáticos das imagens de personagem |

### Persistência
`STUDIO_CHARACTERS/<cid>/`: `character.json` (id, name, style, descriptor, negative, locked_ref,
sheet[], providers{higgsfield:{soul_id,variant}}), `refs/`, `explore/candidates/`, `sheet/candidates/`.
Gitignored, fora de `projects/`.

### Fora do escopo / follow-ups
- Comando `engine faces` (insightface/ArcFace) no `local_ai_engine` — a nota de identidade degrada
  até ele existir.
- Injeção do descritor quando a etapa é usada direto pela tela (hoje a injeção é pelo chat).
- IPAdapter/Redux dedicado por referência no character sheet (hoje ancorado pelo descritor).
