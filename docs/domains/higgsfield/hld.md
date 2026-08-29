### HLD: higgsfield (ponte com o CLI oficial)

Versão: 1.0
Data: 2026-08-25
Responsável: Arthur Diego (pré-preenchido pelo raio-X; aprovado em lote no brownfield)

---

### Objetivo técnico
Dar aos domínios de etapa um único caminho para gerar imagens/vídeos, consultar histórico,
estimar custo e ler o estado da conta na Higgsfield, **exclusivamente** pelo CLI oficial
(`@higgsfield/cli`), conforme a regra da documentação da Higgsfield ("não chamar
`api.higgsfield.ai` com curl"). Nunca automatizar a UI web (o ilimitado do plano é de uso humano
na interface; burlar isso arrisca a conta).

Dependências com outros sistemas
- Binário `higgsfield`/`hf` no `PATH` (npm global, versão 1.1.23 em 2026-08-25).
- Sessão OAuth do usuário (`higgsfield auth login`) e workspace selecionado (`hf workspace set`).
- Consumidores: `mood.service` (hoje); etapas 3–9 (futuro).

---

### Arquitetura geral
Módulo sem estado: cada função monta `[BIN, *args, "--json"]`, executa via `subprocess.run` com
timeout, faz parse do JSON (aceita JSON único ou JSON-lines) e devolve estruturas simples. Leitura
defensiva: `_flatten` achata o JSON e `_pick` busca chaves por nome terminal; URLs de imagem são
extraídas por regex de qualquer campo.

Ambiente de implantação
- Local; herda ambiente do usuário.

Tecnologias principais
- `subprocess`, `json`, `re`, `shutil.which`.

Padrões adotados
- Adapter/anti-corruption layer: o resto do sistema não conhece flags do CLI.
- Mapeamento de parâmetros → flags (`aspect_ratio` → `--aspect-ratio`, listas repetem a flag, bool vira `true|false`).
- Nunca lança exceção para "CLI ausente" em `status()`; lança `RuntimeError` em operações que exigem o CLI.

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `available()` / `status()` | detectar binário; `account status` → instalado/logado/plano/créditos | CLI |
| `history_images(size)` | `generate list --image --size N` → [{id, prompt, model, created, urls[]}] | CLI |
| `model_params(model)` / `adapt_params(model, params)` | `model get <modelo>` (catálogo cacheado 1 h) → só os params que o modelo declara vão ao CLI; param desconhecido (ex.: `mode` no `kling2_6`) é descartado com log, param essencial (`prompt`, `start_image`, `end_image`) não suportado vira `RuntimeError` explicativo em vez de gerar outra coisa | CLI |
| `cost(model, params)` | `adapt_params` + `generate cost` (estimativa sem gastar) | CLI |
| `generate(model, params, timeout)` | `adapt_params` + `generate create … --wait` → {raw, urls, id} | CLI |
| `_params`, `_flatten`, `_pick`, `_json` | utilidades de mapeamento e parse | — |

---

### Fluxo de requisições e de dados
**Fluxo de requisição**
- Serviço de etapa → `hf.generate(model, params)` → subprocess (bloqueante, em thread do chamador) → JSON → URLs → download pelo chamador.

**Fluxo de dados**
- Parâmetros Python → flags CLI → job na Higgsfield → JSON (`--json`) → dict achatado → URLs/ids/custo.

---

### Modelo de dados (alto nível)
Entidades principais
- `Job` (id, model, prompt, urls, custo) — persistido pelo chamador em `projects/<id>/jobs/*.json`.

Relações
- Um `Job` gera N arquivos importados pelo domínio de etapa.

Fonte de verdade
- A Higgsfield (histórico da conta); o repositório guarda cópia do JSON de cada job.

---

### Interfaces públicas
| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `GET /api/higgsfield/status` | API | REST/JSON | Interna | timeout 30 s |
| Funções `status/history_images/cost/generate` | SDK interno | Python | Interna | `generate` timeout padrão 600 s |

---

### Considerações de escalabilidade e disponibilidade
Abordagem geral
- Uma chamada por vez por job; paralelismo fica a cargo do chamador (threads) respeitando limites da conta.

Técnicas aplicadas
- Timeouts explícitos; `--wait-timeout` alinhado ao timeout do subprocess.

Meta de disponibilidade
- Dependente da Higgsfield; erro vira `RuntimeError` com stderr truncado (≤ 400 chars) para a UI.

---

### Segurança
Autenticação
- Delegada ao CLI (OAuth, tokens curtos; `auth login` quando expira).

Autorização
- Workspace de cobrança escolhido no CLI.

Proteção de dados
- Nenhum dado sensível transita pelo módulo além de prompts e URLs; JSON bruto salvo pelo chamador pode conter e-mail da conta (não versionado: `projects/` ignorado).

Gestão de segredos
- Nenhum segredo no repositório; o CLI guarda os seus.

---

### Observabilidade
Logs
- stderr do CLI é devolvido nas exceções; JSON bruto arquivado por job.

Métricas
- Créditos por job (a consolidar em `costs.json`); contagem de falhas por modelo.

Tracing
- Não se aplica.

Dashboards e alertas
- Chip "CLI: plano · créditos" na etapa 2.

---

### Riscos arquiteturais e mitigação
| Risco | Probabilidade | Impacto | Mitigação |
| ----- | ------------- | ------- | --------- |
| Mudança de IDs de modelo/flags entre versões do CLI | Média | Médio | Consultar `model list --json` no bootstrap; não hardcodar além de defaults |
| CLI ausente ou sem login | Alta no primeiro uso | Baixo | `status()` explica; UI desabilita ações pagas |
| Formato de saída não validado com conta logada | Alta | Médio | Parser defensivo; validar e fixar em teste com fixture real na primeira sessão |

---

### ADRs associados e próximos passos
- ADRs em `docs/adrs/generated/HIGGSFIELD/` (CLI-only; nunca API direta nem automação de UI).
- Próximos passos: fixture JSON real para testes; `cost` exposto na UI antes de gerar; `download` por id para vídeos.
