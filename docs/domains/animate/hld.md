### HLD: animate (etapa 6 — animação, aula 012)

Versão: 1.0
Data: 2026-08-25
Responsável: frente OS-006 (wave 1, `/dd-parallel`)

---

### Objetivo técnico
Reproduzir a etapa 6 da aula 012: transformar cada frame escolhido na etapa 5 em **takes de
vídeo**. Por take: prompt simples para cena simples, prompt de movimento elaborado (câmera +
ação) quando não, **start/end frame** entre dois frames seguidos da mesma cena, 10 s para
mudanças lentas, **áudio do modelo OFF**, dois takes por shot, "like" no usável, download e
nome na convenção da wave. Após 3 falhas no mesmo shot o Studio **sugere** o próximo modelo da
ordem (Kling → Seedance → Veo); esgotada a ordem, sugere o corte para preto que a montagem usa
como fallback. Em "modo UI" o usuário gera na interface da Higgsfield (onde vale o ilimitado do
plano) e importa o mp4; o caminho pago pelo CLI é opcional e sempre precedido de estimativa.

Dependências com outros sistemas
- Domínio `shots` (etapa 5): `shots/storyboard.json` é o insumo — cenas e frames ordenados.
- Domínio `edit` (etapa 8): consome `animate/takes.json` e `videos/cenaNN/*`; devolve, quando o
  usuário quer transição colada, PNGs de `edit/last_frames/` que ele escolhe **manualmente**
  como end frame (decisão 4 da wave: sem automação cruzada).
- Domínio `higgsfield`: `generate cost/create` e `generate list --video` via CLI oficial (ADR-002).
- `studio/common/{ingest,jobs,ffmpeg}.py`: ingestão de mídia com dedupe, jobs em thread, thumbs.
- Pasta Downloads do Windows (`/mnt/c/Users/<user>/Downloads`, override `STUDIO_DOWNLOADS`).

---

### Arquitetura geral
Plugin de etapa (`studio/etapas/animate/`) + serviço puro sobre o sistema de arquivos
(`studio/animate/service.py`). O serviço não guarda estado em memória: o plano é sempre
`shots/storyboard.json` mesclado com `animate/takes.json`, gravado de forma atômica. A única
exceção é o job de geração paga, que segue o `JobRegistry` (thread daemon + polling, ADR-006).

Ambiente de implantação
- Local, mesmo processo do `studio` (monólito, ADR-001).

Tecnologias principais
- FastAPI (rotas do plugin), ffmpeg/ffprobe (thumb e duração do candidato), threading (job do
  CLI), CLI oficial da Higgsfield via subprocess.

Padrões adotados
- Regra da aula codificada: `sound: False` sempre, durações {5, 10} (8 só internamente para
  `veo3_1_lite` com start+end), 2 takes por padrão, 3 falhas = troca de modelo **sugerida**.
- Ingestão idempotente por SHA-1 do conteúdo (reimportar o mesmo mp4 não cria take duplicado).
- IDs de modelo fora do código-fonte de rotas: `MODEL_ORDER` com override por
  `STUDIO_ANIMATE_MODELS` (ADR-002, catálogo vivo).
- Nada é apagado: remesclar com um storyboard alterado preserva takes (`orphan: true`).

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `load_plan` / `_merge` | lê o storyboard (defensivo: shot sem frame vira `image: null` + `warnings[]`), ordena cenas/shots, mescla com `takes.json`, grava atômico | `shots/storyboard.json` |
| `suggest_prompt` | template dos três modos da aula (simples, elaborado, start/end) em inglês, com exemplo pt-BR e duração 5/10 | plano |
| `import_upload` / `import_downloads` / `import_history` | ingestão de mp4 com dedupe, thumb e duração | `common/ingest.py` (`kind="video"`), `hf.history_media("video")` |
| `attach_take` / `set_like` | candidato → `videos/cenaNN/shotMM_takeK.mp4`; like grava `shotMM_final.mp4` (um por shot) | `common/ingest.py` |
| `suggested_model` / `failures_of` | contagem de falhas (rejeições + erros do CLI) e sugestão do próximo modelo | — |
| `build_params` | params do `generate create` (sempre `sound: False`; 8 s para `veo3_1_lite` com start+end) | — |
| `cost` / `start_generate` / `job_status` | estimativa antes de gastar; job por projeto com log por take; falha de take não derruba o job | `hf.cost/generate/download`, `JobRegistry` |

---

### Fluxo de requisições e de dados
**Fluxo de requisição (modo UI, caminho padrão)**
- `GET .../animate/shots` → plano → `GET .../animate/prompt` → usuário edita →
  `PUT .../animate/shots/{scene}/{shot}` → gera na UI da Higgsfield →
  `POST .../animate/import/{upload|downloads|history}` → `GET .../animate/candidates` →
  `POST .../animate/shots/{scene}/{shot}/takes` → `POST .../takes/{take}/like`.
- Caminho pago: `POST .../animate/cost` → `confirm()` na UI → `POST .../animate/generate` →
  `GET .../animate/job` (polling de 3 s).

**Fluxo de dados**
- `shots/storyboard.json` → plano → prompt (texto em inglês) → mp4 (UI ou CLI) →
  `animate/candidates/<sha12>.mp4` + `thumbs/` + `candidates.json` →
  `videos/cenaNN/shotMM_takeK.mp4` → like → `videos/cenaNN/shotMM_final.mp4` →
  `animate/takes.json` (contrato de handoff para a etapa 8).

---

### Modelo de dados (alto nível)
`animate/takes.json`
```
{"shots": [{"scene": "cena01", "shot": "shot01", "order": 1, "image": "shots/cena01/shot01_final.png",
            "scene_prompt": "...", "prompt": "...", "mode": "simple|elaborate|start_end",
            "duration": 5|10, "start_end": null | {"start": "...png", "end": "...png"},
            "fallback_black": false, "cli_failures": 0, "orphan": false,
            "takes": [{"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": true|false|null,
                       "model": "kling3_0", "prompt": "...", "duration": 5,
                       "start_end": null, "source": "downloads", "thumb": "...", "candidate_id": "..."}]}]}
```
As chaves do bloco *Provides* de `docs/domains/studio/waves/wave-1.md` (`scene`, `shot`,
`takes[].{id,file,liked,model,prompt,duration,start_end}`) são exatamente as publicadas; o
restante é aditivo e a etapa 8 pode ignorar.

---

### Interfaces públicas
Todas sob `/api/projects/{pid}/animate/` (mais `GET /api/animate/downloads-folder`), JSON, sem
auth (ADR-001):
`GET shots`, `PUT shots/{scene}/{shot}`, `GET prompt`, `GET candidates`,
`POST import/upload` (multipart, ≤ 200 MB), `POST import/downloads`, `POST import/history`,
`POST shots/{scene}/{shot}/takes` (201), `POST shots/{scene}/{shot}/takes/{take}/like`,
`POST cost`, `POST generate` (202), `GET job`.
Contrato completo e semântica de status: seção 5 de `features/animate-fdd.md`; coleção
executável em `postman/animate.postman_collection.json`.

---

### Considerações de escalabilidade e disponibilidade
Uso local, um usuário. Um job de geração por projeto; geração em série de 2 takes por shot com
timeout de 900 s por take (vídeo é lento). A recomendação da própria aula — trabalhar em
paralelo gerando na UI e importando — é o caminho que escala melhor aqui. Respostas síncronas
em menos de 1 s para projetos de até 50 shots.

---

### Segurança
Sem auth, bind em 127.0.0.1 (ADR-001). `pid` validado por `project_dir` (regex + existência) —
nenhum caminho de arquivo vem cru do cliente; `scene`/`shot` só resolvem se existirem no plano.
Upload limitado a 200 MB e às extensões de vídeo de `MEDIA_EXT`. O CLI é chamado por
subprocess com lista de argumentos (sem shell). Nenhum segredo trafega pela etapa.

---

### Observabilidade
- Contadores na própria UI: "N/M shots prontos", `failures` por shot, chip "Tente <modelo>".
- `job["log"]`: uma linha por evento (`started model=…`, `ok url=… · N s`, `failed <stderr>`,
  `duration forced to 8 (veo3_1_lite start+end)`).
- JSON bruto de cada chamada do CLI em `projects/<id>/jobs/animate_<jobid>.json`.
- Logger `studio.animate` (INFO) para import, attach e like.
- Sem métricas/tracing (monólito local, ADR-001/006); `job_id` correlaciona log, JSON bruto e
  `candidates.json`.

---

### Riscos arquiteturais e mitigação
| Risco | Mitigação |
| --- | --- |
| IDs de modelo e flags reais do CLI não confirmados (sem login) | `MODEL_ORDER` por env e `build_params` centralizado; modo UI + importação é o caminho principal e independe do CLI |
| `shots/storyboard.json` divergir do schema publicado | leitura defensiva (`image: null` + `warnings[]`), fixture copiada do `wave-1.md`, ajuste isolado em `_read_storyboard` |
| Geração em série lenta | job por shot, log com tempo por take, timeout de 900 s, falha de take não derruba o job |
| Disco (candidato + take duplicam o arquivo) | dedupe por SHA-1; `attach_take` copia para manter o candidato reutilizável |

---

### ADRs associados e próximos passos
- ADR-001 (monólito local), ADR-002 (Higgsfield só via CLI), ADR-003 (persistência em arquivos),
  ADR-004 (fidelidade ao roteiro), ADR-006 (jobs em thread + polling), ADR-008 (testes sem rede).
- Próximos passos: confirmar `model get kling3_0|seedance_2_0|veo3_1_lite` após login e ajustar
  `STUDIO_ANIMATE_MODELS`/flags sem novo PR de código; na integração da wave, revalidar o
  handoff com o `storyboard.json` real da etapa 5 e o consumo pela etapa 8.
