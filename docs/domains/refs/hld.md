### HLD: refs (etapa 1 — referências, aula 009)

Versão: 1.1 (guia da etapa + fidelidade à aula 009, OS-014)
Data: 2026-08-25
Responsável: Arthur Diego (pré-preenchido pelo raio-X; aprovado em lote no brownfield)

---

### Objetivo técnico
Reproduzir o primeiro passo da aula 009: buscar campanhas reais (o instrutor usa o Pinterest),
salvar o que o usuário gosta "sem ter ideia nenhuma ainda" e organizar em
`refs/brainstorming/`. A automação cobre busca, rolagem e download; a escolha continua humana.

**Wave 2 (OS-014):** a busca passa a começar pela **marca já validada** que a aula usa como ponto de
partida ("Red Bull", depois "Red Bull snow ads"); a segunda fonte citada na aula (aba **Explore do
Midjourney**) entra por upload manual `[extensão]`; e a etapa expõe um **guia** (`guide.py`) que diz o
que a aula manda fazer, o que falta e quais validações passam — calculado por leitura pura dos
artefatos (ADR-003). Textos de tela e `README.md` deixam claro o que é regra da aula e o que é escolha
do Studio (a regra "referência não entra no vídeo final" é do Studio, por direitos autorais).

Dependências com outros sistemas
- Pinterest (site público, via navegador automatizado — sem API oficial adequada).
- Chromium do Playwright em `~/.cache/ms-playwright`; perfil persistente em `STATE_DIR`.
- Domínio `mood` consome `refs/candidates/candidates.json` (itens `selected`) e `refs/brainstorming/`.

---

### Arquitetura geral
Scraper Playwright (contexto persistente, ritmo humano) + serviço de projeto/seleção + job em
thread. Download pelo próprio contexto do navegador (`ctx.request`), com fallback de tamanho
`originals → 736x → 564x → 474x`, dedupe por SHA-1 do conteúdo e thumbnail por Pillow.

Ambiente de implantação
- Local; headless por padrão; login com janela (WSLg) opcional.

Tecnologias principais
- Playwright (sync API), Pillow, threading.

Padrões adotados
- Uma instrução por página: `goto` → pausas aleatórias 1,5–3,5 s → `mouse.wheel` → coleta via `page.evaluate`.
- Teto por termo (`max_per_term`) e parada após 4 rolagens sem novidade.
- Registro incremental: `candidates.json` salvo a cada imagem baixada.

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `pinterest.py` | login, `is_logged_in`, `search` (coleta + download), `_best_url`, `load/save_candidates` | Playwright, Pillow, `config.PINTEREST_PROFILE` |
| `service.py` | criar/listar projetos (layout do curso), `suggest_terms(product, vibe, brand)`, `import_upload` `[extensão]`, jobs de busca e login, `select` → `brainstorming/` + `README.md`, validação de `pid` | `pinterest.py`, `config`, Pillow |
| `etapas/refs/guide.py` | guia da etapa 1 (leitura pura): entradas, saídas, validações da auditoria §1.5 e próxima ação | `common/guide.py` |

---

### Fluxo de requisições e de dados
**Fluxo de requisição**
- `POST /refs/search {terms,max_per_term,headless}` → `start_search` (lock por projeto) → thread → `pinterest.search` → eventos de progresso → `GET /refs/job`.
- `POST /refs/select {ids,notes}` → copia escolhidas para `refs/brainstorming/`, remove desmarcadas, escreve `README.md` (o "por quê" de cada referência é `[extensão]`).
- `POST /refs/import/upload` (multipart) → referências salvas à mão (Explore do MJ e afins) viram candidatas `source: "upload"` `[extensão]`.
- `GET /api/projects/{pid}/guide/refs` → guia da etapa (núcleo chama `etapas/refs/guide.py`).

**Fluxo de dados**
- Termo → página de busca → `img[src*=pinimg]` → URL `/originals/` → bytes → `refs/candidates/<sha12>.jpg` + `thumbs/<sha12>.jpg` → `candidates.json` → galeria → seleção → `refs/brainstorming/`.

---

### Modelo de dados (alto nível)
Entidades principais
- `Candidate` (id sha12, source, term, url, pin_url, alt, file, thumb, width, height, selected).
- `Project` (do domínio `studio`).

Relações
- `Project` 1 — N `Candidate`; `Candidate.selected` ⇔ cópia existe em `refs/brainstorming/`.

Fonte de verdade
- `refs/candidates/candidates.json`; `brainstorming/` é derivado (regravado a cada `select`).

---

### Interfaces públicas
| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `POST /api/projects/{pid}/refs/search` | API | REST/JSON | Interna | 1 job por projeto; 5–100 imagens/termo |
| `GET /api/projects/{pid}/refs/job` | API | REST/JSON | Interna | polling 2 s |
| `GET /api/projects/{pid}/refs/candidates` | API | REST/JSON | Interna | — |
| `POST /api/projects/{pid}/refs/select` | API | REST/JSON | Interna | — |
| `POST /api/projects/{pid}/refs/import/upload` | API | multipart | Interna | `[extensão]`; ≤ 25 MB por arquivo; só imagens |
| `GET /api/suggest-terms?product&vibe&brand` | API | REST/JSON | Interna | `brand` (aula 009) primeiro, produto como complemento |
| `POST/GET /api/pinterest/login` | API | REST/JSON | Interna | espera até 5 min pelo cookie `_auth` |

---

### Considerações de escalabilidade e disponibilidade
Abordagem geral
- Volume baixo por desenho (40–80 imagens por campanha) para não chamar atenção do Pinterest.

Técnicas aplicadas
- Dedupe por URL e por hash; `--disable-blink-features=AutomationControlled`; user-agent de desktop.

Meta de disponibilidade
- Best-effort: o DOM do Pinterest muda sem aviso; falha é reportada no job e não derruba o app.

---

### Segurança
Autenticação
- Sessão do usuário no Pinterest (cookie `_auth`), guardada em perfil persistente local.

Autorização
- Não se aplica.

Proteção de dados
- Perfil do navegador fora do repositório; imagens são referência de mood, nunca output.
- Termos de uso do Pinterest: automação contraria; risco assumido pelo usuário (conta secundária recomendada). Registrado em ADR.

Gestão de segredos
- Nenhum segredo em código; cookies só no perfil local.

---

### Observabilidade
Logs
- Eventos de progresso em memória (`start`, `term`, `download`, `saved`, `done`), expostos por `/job`.

Métricas
- `total` de candidatas por job; futuro: taxa de falha de download por tamanho.

Tracing
- Não se aplica.

Dashboards e alertas
- Barra de progresso e log na tela da etapa 1.

---

### Riscos arquiteturais e mitigação
| Risco | Probabilidade | Impacto | Mitigação |
| ----- | ------------- | ------- | --------- |
| Mudança do DOM/anti-bot do Pinterest | Alta | Médio | Seletor genérico por `pinimg.com`; fallback planejado: SerpAPI/Pexels |
| Bloqueio da conta | Média | Médio | Ritmo humano, teto por termo, conta secundária |
| Sem login, `pin_url` vazio ("gated pins") | Certa | Baixo | Documentado; URL da imagem sempre registrada |

---

### ADRs associados e próximos passos
- ADRs em `docs/adrs/generated/REFS/` (scraping vs API; dedupe por conteúdo).
- Próximos passos: fonte alternativa com API (SerpAPI/Pexels) como fallback; testes de `_collect_from_page` com HTML fixo.
