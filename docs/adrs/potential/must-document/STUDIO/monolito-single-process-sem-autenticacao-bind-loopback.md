# Potencial ADR: Monólito Modular Single-Process, Sem Autenticação, Bind em Loopback

**Módulo**: STUDIO
**Categoria**: Arquitetura
**Prioridade**: Must Document (Score: 150/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: sim — confirmar se há intenção futura de expor a
ferramenta além de `127.0.0.1`/uso single-user (multiusuário, acesso remoto, deploy hospedado);
se sim, esta decisão precisa ser revista antes de qualquer exposição, pois hoje não há nenhuma
camada de autenticação/autorização.

**Data de identificação**: 2026-08-25

## Contexto

O Orquestrador Studio é servido como um único processo (`uvicorn studio.app:app`), com bind
padrão em `127.0.0.1`, porta `8765` (configurável via `PORT`), iniciado por `run.sh`/`make run`.
O backend FastAPI (`studio/app.py`) e o frontend — uma SPA estática vanilla (HTML/CSS/JS, sem
framework, sem bundler, sem etapa de build) em `studio/web/` — são servidos pelo mesmo processo:
o frontend é montado via `StaticFiles` em `/static` e a `index.html` é servida diretamente na
rota raiz `/` via `FileResponse`. Não há separação de deploy entre frontend e backend, não há
build step (TypeScript, bundler, minificação) e não há nenhuma camada de autenticação ou
autorização em nenhuma rota `/api/*` — qualquer processo que consiga alcançar a porta 8765 tem
acesso total à API, incluindo criação/leitura de projetos e disparo de jobs que consomem créditos
pagos da Higgsfield.

Essa é uma decisão coerente e deliberada com o restante do projeto: é uma "ferramenta local (não
é um produto multiusuário nem hospedado)" (mapping.md, linha 14), pensada para rodar na máquina
do próprio usuário via WSL2 ou Linux, uma instância por checkout. O `docs/gitflow.md` reforça
essa premissa ao definir que execução paralela em múltiplas worktrees usa portas diferentes a
partir de `8766`, sempre em loopback — nunca um cenário de exposição de rede compartilhada. Este
modelo está presente desde o primeiro commit (`b29700a`) e nunca foi alterado ao longo do
histórico do projeto.

## Decisão

Servir a API FastAPI e o frontend estático no mesmo processo, sem separação de deploy, sem etapa
de build de frontend, com bind padrão em `127.0.0.1` e sem nenhuma camada de autenticação ou
autorização — a segurança de acesso depende inteiramente do isolamento de rede da máquina local
do usuário.

## Alternativas Consideradas

Não há evidência de que autenticação (mesmo básica, tipo HTTP Basic Auth) ou separação de
frontend/backend em deploys distintos tenha sido avaliada e descartada por escrito. A escolha é
plausível e coerente com o objetivo declarado do produto (ferramenta local single-user), mas não
há um comentário, config ou README que discuta explicitamente o trade-off de segurança — a
decisão parece ter sido implícita desde a concepção do projeto, não uma escolha revisitada.

## Consequências

### Positivas
- Simplicidade máxima de execução: `./run.sh` ou `make run` sobem tudo, sem orquestração de
  múltiplos serviços, sem CORS a configurar entre frontend/backend, sem gerenciamento de sessão.
- Sem etapa de build de frontend: qualquer alteração em `app.js`/`index.html`/`style.css` é
  visível imediatamente após reload do navegador, sem pipeline de transpilação/bundling.
- Adequado ao caso de uso real e único documentado: um usuário, uma máquina, um checkout por vez
  (ou várias worktrees em portas diferentes, todas ainda em loopback).
- Reduz drasticamente a superfície de configuração de segurança que precisaria ser mantida
  corretamente (não há tokens, sessões, chaves JWT, nem lógica de expiração para acertar).

### Negativas / Trade-offs
- Zero autenticação/autorização: se a porta 8765 for exposta além de `127.0.0.1` por qualquer
  motivo (ex.: erro de configuração de firewall, port-forward em container, WSL com bind
  incorreto), qualquer agente na rede tem acesso total — incluindo a capacidade de disparar
  geração de imagem via CLI da Higgsfield, que **gasta créditos pagos** do usuário
  (`mood_generate`, `studio/app.py` linha 190).
- `PROJECTS_DIR` inteiro é servido publicamente via `/files` (ver decisão de "Persistência em
  Sistema de Arquivos") sem nenhum controle de acesso adicional — qualquer dado de projeto salvo
  em disco é acessível por HTTP a quem alcançar a porta.
- Sem separação de deploy, escalar o frontend independentemente do backend (CDN, cache HTTP
  agressivo, deploy hospedado) exigiria repensar a arquitetura de ponta a ponta.
- Frontend sem framework/TypeScript/testes de tipo significa que mudanças de contrato na API
  (`studio/app.py`) não são pegas em tempo de build pelo `app.js` — o relatório de auditoria de
  dependências já observa isso explicitamente (seção 6, item 9: "não há nenhuma rede de proteção
  de tipos").

## Evidências no Código

### Arquivos-chave
- `studio/app.py` (linhas 216-222) — montagem de `/files` e `/static` e rota `/` no mesmo `app`
  FastAPI, sem nenhum `Depends()` de autenticação em nenhuma rota
- `run.sh` — inicialização única via `uvicorn studio.app:app`, bind padrão `127.0.0.1:8765`
- `docs/gitflow.md` (linhas 104-107) — "Execução paralela": portas a partir de `8766`, sempre em
  loopback, nunca cenário de rede compartilhada
- `studio/web/index.html`, `studio/web/app.js` — frontend vanilla sem framework/build, servido
  como arquivo estático pelo mesmo processo

### Trecho de código
```python
# studio/app.py — nenhuma rota tem dependência de autenticação
@app.post("/api/projects/{pid}/mood/generate")
def mood_generate(pid: str, req: MoodGenReq):
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    root = service.project_dir(pid)
    refs = [str(p) for p in sorted((root / "refs" / "brainstorming").glob("*.jpg"))[:6]] if req.use_refs else None
    try:
        return mood.start_generate(pid, req.model, req.prompts, req.aspect_ratio, req.resolution, req.count, refs)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e

# arquivos dos projetos (thumbs e originais) e frontend, ambos sem controle de acesso
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:31:34 (commit `b29700a`, scaffold inicial) — modelo de processo
  único e sem autenticação presente desde o início
- Modificado: `studio/app.py` recebeu 4 commits ao todo (`b29700a`, `2b5fd95`, `54b42c1`,
  `155a787`), nenhum deles introduzindo autenticação, CORS restritivo ou separação de deploy
- Última mudança: 2026-08-25 02:44:56 (`155a787`), foco em validação de negócio (limites de
  seleção, geração concorrente), não em segurança de acesso
- Estável ao longo de todo o histórico observável do projeto

## ADRs Relacionados / Potenciais

- Relaciona-se diretamente com "Persistência em Sistema de Arquivos, sem Banco de Dados" — o
  mesmo `PROJECTS_DIR` exposto sem autenticação via `/files` é o mesmo diretório usado como
  fonte única de persistência de negócio.
- Relaciona-se com "Fidelidade ao Roteiro do Curso" — reforça o enquadramento do produto como
  ferramenta pessoal de um único usuário, não um produto multiusuário.

## Notas Adicionais

Esta é a decisão com maior potencial de dano se o contexto do produto mudar (ex.: se em algum
momento o usuário decidir hospedar uma instância compartilhada, ou expor a máquina via túnel/
port-forward para acesso remoto próprio) sem que a ausência de autenticação seja revisitada
explicitamente. Recomenda-se que uma ADR formal desta decisão declare explicitamente o limite de
uso pretendido (rede confiável/loopback apenas) como pré-condição da decisão, para que qualquer
mudança futura de ambiente de execução force a revisão.
