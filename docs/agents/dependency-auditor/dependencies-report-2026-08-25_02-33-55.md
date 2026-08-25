# Relatório de Auditoria de Dependências — Orquestrador Studio

**Data da auditoria:** 2026-08-25 02:33:55
**Escopo analisado:** `/home/arthu/code/senhortecnologia/orquestrador-studio`
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`
**Auditor:** dependency-auditor (análise e relatório apenas; nenhum arquivo do projeto foi modificado)

---

## 1. Resumo

O **Orquestrador Studio** é uma ferramenta local composta por:

- **Backend**: Python 3.12, framework **FastAPI** servido por **Uvicorn**, com automação de navegador via **Playwright** (scraping do Pinterest) e processamento de imagem via **Pillow**. Upload de arquivos multipart é habilitado por **python-multipart**.
- **Frontend**: HTML/CSS/JS estático em `studio/web/` (sem `package.json`, sem gerenciador de pacotes, sem build step). O único recurso externo carregado é uma folha de estilo do Google Fonts via CDN (`fonts.googleapis.com`) — não é uma dependência de pacote, mas um recurso de rede em tempo de execução.
- **Integração externa**: o CLI `@higgsfield/cli` (instalado globalmente via `npm i -g`, versão citada no `README.md` como `1.1.23`) é invocado via `subprocess` a partir de `studio/higgsfield.py`. Conforme instrução do escopo, **não é um dependency do projeto** (não consta em nenhum manifesto do repositório) e por isso não entra na tabela de dependências, mas é tratado como ponto de integração externo e risco de ponto único de falha (seção 6).

O único manifesto de dependências Python encontrado foi `requirements.txt` (5 entradas diretas, sem pins de versão). Não há `pyproject.toml`, `Pipfile`, `poetry.lock` nem lockfile de nenhum tipo para o ecossistema Python. Não há `package.json`/lockfile para o frontend, pois este não possui dependências de pacote (JS puro, sem bibliotecas externas).

As versões efetivamente instaladas no ambiente virtual (`.venv`) foram obtidas via `pip list --format=freeze` e comparadas com a última versão estável publicada no PyPI (consulta direta à API JSON do PyPI em 2026-08-25). **Todas as 5 dependências diretas estão na versão mais recente disponível no PyPI** no momento da auditoria. Não foram encontradas vulnerabilidades ativas (CVE não corrigido) afetando as versões instaladas — Pillow 12.3.0 e python-multipart 0.0.32, em particular, já incorporam as correções dos CVEs mais recentes divulgados para essas bibliotecas em 2026 (detalhes na seção 2/4).

Achado de maior atenção não é técnico-dependencial, mas de **reprodutibilidade e governança**: (a) ausência de lockfile/pins de versão no `requirements.txt` (todas as entradas estão sem restrição de versão), o que significa que qualquer novo `pip install` pode trazer versões diferentes das auditadas aqui, inclusive breaking changes; e (b) dependência funcional de um binário externo não versionado no repositório (`@higgsfield/cli`), que é um ponto único de falha para a Etapa 2 do fluxo do curso.

Não foram detectadas dependências obsoletas (deprecated), sem manutenção há mais de um ano, ou com problemas de licenciamento.

---

## 2. Questões Críticas

Nenhuma vulnerabilidade **ativa/não corrigida** foi identificada nas versões atualmente instaladas. Os itens abaixo são relevantes para conhecimento e monitoramento, não para ação imediata:

- **Starlette (transitiva do FastAPI) — CVE-2026-48710 ("BadHost")**: bypass de autenticação via cabeçalho `Host` malformado, afetando Starlette `0.8.3` até `1.0.0`. A versão transitiva instalada é **Starlette 1.6.0**, já corrigida (>= 1.0.1). Não representa risco atual, mas evidencia a importância de manter o FastAPI atualizado, pois o fix depende da cadeia de dependência transitiva e não é controlado diretamente pelo `requirements.txt` do projeto.
- **Pillow — série de CVEs 2026 (CVE-2026-40192, CVE-2026-25990, CVE-2026-42308, CVE-2026-42309, CVE-2026-59203, CVE-2026-59205, CVE-2026-55798)**: cobrem DoS (decompression bomb em FITS, loop infinito em EPS), buffer overflow (PSD, fontes, ImageCms) e um RCE via injeção de comando no `WindowsViewer`. Todas essas falhas afetam faixas de versão anteriores a **12.2.0/12.3.0**. A versão instalada, **Pillow 12.3.0**, já contém a correção de todas elas (confirmado nas notas de release oficiais do Pillow 12.3.0). Não representa risco atual — listado aqui apenas porque a superfície de ataque (parsing de imagens de origem não confiável, como as baixadas do Pinterest em `studio/refs/pinterest.py`) torna o Pillow um componente sensível a monitorar em cada futura atualização.
- **python-multipart — histórico de CVEs (ReDoS CVE-2024-24762, DoS CVE-2024-53981, DoS por preâmbulo/epílogo CVE-2026-40347, path traversal CVE-2026-24486, headers sem limite CVE-2026-42561)**: todas corrigidas em versões iguais ou anteriores a `0.0.26`. A versão instalada, **0.0.32**, está corrigida para todas elas.
- **Ausência de lockfile Python**: sem `requirements.lock`, `poetry.lock` ou hashes de pin, builds futuros do `requirements.txt` não são reprodutíveis — uma reinstalação pode trazer uma versão diferente (potencialmente vulnerável ou com breaking changes) sem que isso fique visível no controle de versão.
- **Dependência funcional de binário externo não gerenciado (`@higgsfield/cli`)**: `studio/higgsfield.py` localiza o binário via `shutil.which("higgsfield") or shutil.which("hf")` e não valida nem fixa uma versão mínima/compatível. Qualquer mudança de contrato de saída JSON do CLI (breaking change externo, fora do controle do projeto) quebra silenciosamente a Etapa 2 do fluxo.

Nenhum item acima exige correção de código — são observações de superfície de risco e governança, não vulnerabilidades exploráveis nas versões atuais.

---

## 3. Dependências

Dependências **diretas** declaradas em `requirements.txt` (sem pin de versão no manifesto). Versão atual = instalada no `.venv` via `pip list --format=freeze`; versão mais recente = consultada na API JSON oficial do PyPI (`pypi.org/pypi/<pkg>/json`) em 2026-08-25.

| Dependência | Versão Declarada (requirements.txt) | Versão Instalada (.venv) | Última Versão (PyPI) | Status |
|---|---|---|---|---|
| fastapi | sem pin | 0.141.1 | 0.141.1 | Atualizada |
| uvicorn[standard] | sem pin | 0.52.4 | 0.52.4 | Atualizada |
| playwright | sem pin | 1.62.0 | 1.62.0 | Atualizada |
| pillow | sem pin | 12.3.0 | 12.3.0 | Atualizada |
| python-multipart | sem pin | 0.0.32 | 0.0.32 | Atualizada |

Todas as 5 dependências diretas estão na última versão estável publicada. Nenhuma está obsoleta, descontinuada (deprecated) ou legada.

Observação sobre `uvicorn[standard]`: o extra `[standard]` traz um conjunto de dependências transitivas (`uvloop`, `httptools`, `watchfiles`, `websockets`, `python-dotenv`, `PyYAML`) que, conforme critério do escopo, **não entram na tabela de diretas**, mas foram inspecionadas via `pip freeze` e não apresentam CVEs ativos nas versões instaladas.

### Licenciamento (dependências diretas)

| Dependência | Licença | Compatibilidade |
|---|---|---|
| fastapi | MIT | Permissiva, sem restrição para uso comercial/fechado |
| uvicorn | BSD-3-Clause | Permissiva, sem restrição para uso comercial/fechado |
| playwright | Apache License 2.0 | Permissiva, sem restrição para uso comercial/fechado |
| pillow | HPND (Historical Permission Notice and Disclaimer) | Permissiva, equivalente a MIT em termos de uso comercial |
| python-multipart | Apache License 2.0 | Permissiva, sem restrição para uso comercial/fechado |

Nenhum risco legal identificado: todas as licenças diretas são permissivas e compatíveis entre si e com uso comercial/fechado.

---

## 4. Análise de Riscos

| Severidade | Dependência | Questão | Detalhes |
|---|---|---|---|
| Baixa | requirements.txt (manifesto) | Ausência de pin de versão | Nenhuma das 5 dependências diretas tem versão fixada (`==`) nem há lockfile. Uma nova instalação em outra máquina/momento pode obter versões diferentes das auditadas, sem garantia de reprodutibilidade nem de que o novo conjunto foi testado. |
| Baixa | Pillow | Superfície de ataque em parsing de imagem | Componente processa imagens de origem externa não confiável (baixadas do Pinterest). Já corrigido na versão instalada (12.3.0), mas é o tipo de dependência que historicamente concentra CVEs de parsing (7 CVEs distintos catalogados só em 2026) — merece atenção prioritária em futuras atualizações. |
| Informativa | Starlette (transitiva via FastAPI) | CVE-2026-48710 já corrigido | Instalada em 1.6.0, corrigida; citada apenas porque é uma dependência transitiva crítica de segurança (bypass de autenticação) fora do controle direto do `requirements.txt`. |
| Média | `@higgsfield/cli` (fora do escopo formal de dependências do projeto) | Ponto único de falha / sem versionamento no repositório | Ferramenta externa instalada globalmente via npm, localizada em runtime via `shutil.which`. Sem pin de versão, sem verificação de compatibilidade, sem fallback caso o binário não exista ou mude seu contrato de saída JSON — `studio/higgsfield.py` já implementa parsing defensivo (`_json`) para mitigar parcialmente, mas o card do README já registra que a integração "ainda não [foi] validada com uma conta logada". |
| Baixa | Playwright (automação Pinterest) | Risco de ToS/negócio, não de dependência | Não é uma vulnerabilidade de software: o próprio `README.md` do projeto avisa que "automatizar o Pinterest contraria os termos de uso dele; o risco é da conta usada". Citado aqui porque concentra a maior superfície de automação externa do projeto (`studio/refs/pinterest.py`), tornando-o o arquivo mais sensível a mudanças de layout/anti-bot do Pinterest — risco operacional, não de CVE. |

Nenhum item de severidade **Crítica** ou **Alta** foi identificado nas dependências diretas ou nas transitivas inspecionadas.

---

## 5. Dependências Não Verificadas

Não há dependências não verificadas. As 5 dependências diretas (`fastapi`, `uvicorn[standard]`, `playwright`, `pillow`, `python-multipart`) e as principais transitivas do extra `[standard]` do Uvicorn foram confirmadas contra a API oficial do PyPI e/ou fontes de segurança (SentinelOne, GitHub Advisory Database, GitLab Advisories, notas de release oficiais).

O CLI `@higgsfield/cli` não foi submetido ao mesmo nível de verificação por estar formalmente fora do escopo de auditoria (não é dependência do projeto, é ferramenta externa/global). Buscas na web trouxeram números de versão inconsistentes entre fontes (npm listando `1.1.13`, GitHub Releases listando `v1.1.20`, README do projeto citando `1.1.23`), o que não foi possível reconciliar com certeza nesta auditoria — registrado aqui como observação, não como item da tabela de dependências do projeto.

---

## 6. Análise de Arquivos Críticos

O projeto é pequeno (10 arquivos Python, 975 linhas de código no total, mais 3 arquivos de frontend estático). Todos os arquivos com uso relevante de dependências foram analisados; os listados abaixo são os que concentram maior impacto de negócio, maior superfície de integração externa ou maior densidade de uso de dependências.

1. **`studio/app.py`** (186 linhas) — Ponto de entrada da API (`FastAPI(title="Orquestrador Studio")`). Concentra o uso de `fastapi` (`FastAPI`, `HTTPException`, `UploadFile`, `File`, `Form`, `FileResponse`, `StaticFiles`) e, indiretamente, `python-multipart` (via `UploadFile`/`Form` em `mood_upload`, linha 134). É o arquivo de maior impacto de negócio: qualquer regressão de compatibilidade em uma atualização futura do FastAPI/Starlette quebra todas as rotas da aplicação de uma vez.

2. **`studio/refs/pinterest.py`** (216 linhas) — Scraper Playwright do Pinterest; único arquivo que abre um navegador Chromium controlado (`playwright`) e também processa as imagens baixadas com `Pillow` (geração de miniaturas). É o arquivo com maior superfície de risco combinada: automação de terceiro sujeita a mudanças de layout/anti-bot (risco operacional) *e* parsing de imagens de origem não confiável via Pillow (a categoria de dependência com mais CVEs catalogados em 2026, ainda que corrigidos na versão instalada).

3. **`studio/mood/service.py`** (245 linhas) — Maior arquivo do projeto. Usa `Pillow` para extração de paleta de cores (`palette.json`) das imagens de mood board e integra com o módulo `higgsfield.py`. Concentra lógica de negócio da Etapa 2 do curso e depende tanto do Pillow quanto da disponibilidade do CLI externo.

4. **`studio/higgsfield.py`** (135 linhas) — Ponte via `subprocess` com o CLI externo `@higgsfield/cli`/`hf`, não gerenciado como dependência do projeto (sem pin, sem lockfile, instalação global via npm). É o único ponto único de falha (SPOF) externo ao ecossistema Python auditado: se o binário mudar seu contrato de JSON ou for desinstalado, a etapa 2 falha silenciosamente até o parsing defensivo (`_json`) capturar o erro.

5. **`studio/refs/service.py`** (143 linhas) — Orquestra projetos, jobs e seleção de imagens; consome os resultados de `pinterest.py` e depende transitivamente de Pillow (miniaturas) e da estrutura de diretórios criada por `config.py`. Ponto de acoplamento entre o scraper e a API.

6. **`requirements.txt`** — Não é código, mas é o único manifesto de dependências Python do projeto e não possui pins de versão nem lockfile associado. É o arquivo "crítico" do ponto de vista de governança de dependências: uma reinstalação futura (`pip install -r requirements.txt`) pode alterar todas as 5 dependências diretas (e suas transitivas) sem qualquer registro do que mudou.

7. **`run.sh`** — Único ponto de inicialização do servidor (`exec uvicorn studio.app:app ...`). Concentra a dependência de `uvicorn[standard]` em runtime; qualquer incompatibilidade de CLI do Uvicorn entre versões afeta diretamente a capacidade de subir a aplicação.

8. **`studio/web/index.html`** — Único arquivo do frontend que carrega um recurso de rede externo não versionado no repositório (Google Fonts via CDN, linha 7). Não é uma dependência de pacote gerenciada, mas é o único ponto de falha externo do frontend (indisponibilidade do CDN degrada a tipografia, sem quebrar funcionalidade).

9. **`studio/web/app.js`** (232 linhas) — Toda a lógica de frontend (chamadas `fetch` para a API FastAPI, incluindo upload multipart na linha 196). Não tem dependências de pacote JS (vanilla JS), mas é o único consumidor direto dos contratos de API expostos por `studio/app.py`; uma mudança breaking no FastAPI que altere formatos de resposta afeta este arquivo sem nenhuma rede de proteção de tipos (não há testes E2E nem contrato TypeScript).

10. **`studio/config.py`** (20 linhas) — Define os caminhos (`STUDIO_PROJECTS`, `STUDIO_STATE`) usados por praticamente todos os módulos acima. Pequeno, mas é uma dependência interna transversal: qualquer mudança de comportamento de biblioteca de path/IO do stdlib usada aqui afeta toda a árvore de módulos.

---

## 7. Notas de Integração

- **fastapi + uvicorn**: `studio/app.py` define a aplicação; `run.sh` a serve via `uvicorn studio.app:app`. Uso direto e simples, sem middlewares de terceiros além dos módulos nativos do FastAPI (`StaticFiles`, `FileResponse`).
- **python-multipart**: usado apenas indiretamente através de `UploadFile`/`Form` do FastAPI (rota `mood_upload`, `studio/app.py:134`) — é uma dependência exigida pelo próprio Starlette/FastAPI para suportar `multipart/form-data`, sem uso direto de sua API no código do projeto.
- **playwright**: usado exclusivamente em `studio/refs/pinterest.py` para abrir um Chromium com perfil persistente (`~/.orquestrador-studio/pinterest-profile`), simulando navegação humana para buscar e baixar imagens do Pinterest. Não há uso de Playwright para testes automatizados do próprio projeto — é usado como motor de automação de produto, não como ferramenta de QA.
- **pillow**: usado em `studio/refs/pinterest.py` (geração de miniaturas das imagens baixadas) e em `studio/mood/service.py` (extração de paleta de cores dominante para `mood/palette.json`).
- **@higgsfield/cli (fora do escopo formal)**: acessado exclusivamente via `subprocess` em `studio/higgsfield.py`, seguindo a regra documentada no próprio código-fonte ("nunca chamar api.higgsfield.ai direto; o CLI cuida de auth, upload e polling"). É o único ponto de integração do projeto com um serviço de IA generativa de terceiros.
- **Google Fonts (CDN, frontend)**: carregado via `<link>` em `studio/web/index.html`; não é dependência de pacote, é um recurso de rede externo sem fallback local.

---

## 8. Confirmação de Salvamento do Relatório

Relatório salvo com sucesso em:

`/home/arthu/code/senhortecnologia/orquestrador-studio/docs/agents/dependency-auditor/dependencies-report-2026-08-25 02:33:55.md`

Nenhum arquivo do projeto (código, manifestos ou configuração) foi alterado durante esta auditoria.
