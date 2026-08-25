### HLD: mood (etapa 2 — mood board, aula 009)

Versão: 1.0
Data: 2026-08-25
Responsável: Arthur Diego (pré-preenchido pelo raio-X; aprovado em lote no brownfield)

---

### Objetivo técnico
Reproduzir o mood board da aula 009: **uma vibe** para a campanha inteira, obtida com um único
prompt de ambiente/luz/cor (sem produto, sem pessoas), gerado em grid de 4, com regeração quando
"não pegou a vibe". Em "modo UI", o Studio entrega o prompt, o usuário gera na interface da
Higgsfield (onde o ilimitado do plano vale) e o resultado é importado; alternativamente o CLI
gera pagando créditos. Produto na cena, escala e rótulo pertencem à etapa 3.

Dependências com outros sistemas
- Domínio `refs`: referências escolhidas alimentam o prompt (termos e descrições úteis).
- Domínio `higgsfield`: histórico de jobs (`generate list --image`) e geração (`generate create`).
- Pasta Downloads do Windows (`/mnt/c/Users/<user>/Downloads`, override `STUDIO_DOWNLOADS`).

---

### Arquitetura geral
Serviço puro sobre o sistema de arquivos: gera prompt (template + variações de estilização),
ingere imagens de três fontes (upload, Downloads recentes, histórico do CLI) com dedupe por
SHA-1 e thumbnail, e consolida a seleção em `mood/selected/`, `palette.json` (cores dominantes
por quantização Pillow) e `mood.md`.

Ambiente de implantação
- Local, mesmo processo do `studio`.

Tecnologias principais
- Pillow (thumbnail, quantização MEDIANCUT), threading (geração via CLI), urllib (download de URLs do CLI).

Padrões adotados
- Regra de negócio do curso codificada: 1 prompt, variações só de estilo, teto de 8 imagens no mood.
- Ingestão idempotente (`_ingest_bytes` ignora conteúdo repetido).
- Fontes de importação desacopladas: cada uma só produz `(nome, bytes, metadados)`.

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `suggest_prompts` | prompt de vibe a partir de `project.json` + referências selecionadas (filtra alt "Salvar Pins"); `variation` troca a estilização | `refs/candidates.json` |
| `import_upload` / `import_downloads` / `import_history` | ingestão com dedupe, thumbnails, metadados de origem | Pillow, `higgsfield.history_images` |
| `start_generate` / `job_status` | geração paga via CLI em thread, download das URLs, registro em `jobs/mood_<id>.json` | `higgsfield.generate` |
| `select` | copia escolhidas, limita a 8, gera paleta e `mood.md` | Pillow |

---

### Fluxo de requisições e de dados
**Fluxo de requisição**
- `GET /mood/prompts?model&variation` → prompt → usuário copia → gera na UI → `POST /mood/import/downloads` (ou upload/history) → `GET /mood/candidates` → `POST /mood/select`.
- Caminho pago: `POST /mood/generate` → thread → `GET /mood/job`.

**Fluxo de dados**
- Referências + projeto → prompt (texto) → imagens (UI/CLI) → `mood/candidates/<sha12>.<ext>` + `thumbs/` → `candidates.json` → `mood/selected/` + `palette.json` + `mood.md`.

---

### Modelo de dados (alto nível)
Entidades principais
- `MoodCandidate` (id, source ∈ {upload, downloads, higgsfield, cli}, name, prompt, file, thumb, width, height, selected, imported, job_id?, model?, origin_path?).
- `Palette` (colors[6], note).

Relações
- `Project` 1 — N `MoodCandidate`; `selected` ⇔ cópia em `mood/selected/`.

Fonte de verdade
- `mood/candidates.json`; `selected/`, `palette.json` e `mood.md` são derivados de `select`.

---

### Interfaces públicas
| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `GET /api/projects/{pid}/mood/prompts` | API | REST/JSON | Interna | — |
| `POST …/mood/import/upload` | API | multipart | Interna | ≤ 25 MB por arquivo; só imagens |
| `POST …/mood/import/downloads` | API | REST/JSON | Interna | últimos N minutos, ≤ 40 arquivos |
| `POST …/mood/import/history` | API | REST/JSON | Interna | exige CLI logado; 502 se falhar |
| `POST …/mood/generate`, `GET …/mood/job` | API | REST/JSON | Interna | gasta créditos; confirmação na UI |
| `POST …/mood/select` | API | REST/JSON | Interna | ≤ 8 ids (422 acima) |

---

### Considerações de escalabilidade e disponibilidade
Abordagem geral
- Dezenas de imagens por projeto; sem necessidade de paginação.

Técnicas aplicadas
- Thumbnails 520 px; dedupe por hash evita reimportar a mesma imagem do Downloads.

Meta de disponibilidade
- Importação do histórico depende do CLI; falha é 502 e não afeta as outras fontes.

---

### Segurança
Autenticação
- Nenhuma própria; o CLI da Higgsfield carrega a sessão do usuário.

Autorização
- Não se aplica.

Proteção de dados
- Downloads: só extensões de imagem, só arquivos recentes; caminho de origem registrado.
- URLs do histórico baixadas sem allowlist de domínio (risco registrado; próximo passo).

Gestão de segredos
- Nenhum.

---

### Observabilidade
Logs
- `job.log[]` para falhas de download na geração; `jobs/mood_<id>.json` guarda o JSON bruto do CLI (custo incluído).

Métricas
- Imagens por fonte; créditos por job (a consolidar em `costs.json`).

Tracing
- Não se aplica.

Dashboards e alertas
- Contadores na tela (candidatas/escolhidas) e paleta.

---

### Riscos arquiteturais e mitigação
| Risco | Probabilidade | Impacto | Mitigação |
| ----- | ------------- | ------- | --------- |
| Formato JSON do `generate list` desconhecido (não validado logado) | Alta | Médio | Parser defensivo (varre URLs de imagem); validar na primeira sessão logada |
| Ilimitado da UI não vale no CLI — usuário gasta créditos sem querer | Média | Médio | Botão pago pede confirmação; `generate cost` antes de gerar (próximo passo) |
| Desvio do roteiro (voltar a múltiplos prompts) | Baixa | Alto | Teste `test_mood_prompt_is_single_vibe_without_product` + gate no CLAUDE.md |

---

### ADRs associados e próximos passos
- ADRs em `docs/adrs/generated/MOOD/` (modo UI vs automação; um prompt por vibe).
- Próximos passos: estimativa de custo antes de gerar; allowlist de domínios de download; etapa 3 (imagem base) consome `mood/selected/` e `palette.json`.
