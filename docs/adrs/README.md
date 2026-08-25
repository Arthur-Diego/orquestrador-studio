# Índice de ADRs — Orquestrador Studio

Este documento indexa as Architecture Decision Records (ADRs) geradas para o `orquestrador-studio`,
organizadas por módulo, e mostra o grafo de relacionamentos entre elas.

## Índice

| Número  | Título                                                                                                    | Módulo     | Status  | Link                                                                                                                     |
| ------- | ---------------------------------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| ADR-001 | Monólito Single-Process, Local, Sem Autenticação, Bind em Loopback                                          | STUDIO     | Aceito  | [generated/STUDIO/ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md](./generated/STUDIO/ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md) |
| ADR-002 | Integração com a Higgsfield somente via CLI oficial (nunca API HTTP direta ou automação de UI)              | HIGGSFIELD | Aceito  | [generated/HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md](./generated/HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md) |
| ADR-003 | Persistência em Sistema de Arquivos, sem Banco de Dados                                                     | STUDIO     | Aceita  | [generated/STUDIO/ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md](./generated/STUDIO/ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md) |
| ADR-004 | Fidelidade ao Roteiro do Curso como Restrição Arquitetural                                                  | STUDIO     | Aceito  | [generated/STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md](./generated/STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md) |
| ADR-005 | Coleta de Referências do Pinterest via Scraping com Playwright (em vez de API)                              | REFS       | Aceito  | [generated/REFS/ADR-005-scraping-pinterest-via-playwright.md](./generated/REFS/ADR-005-scraping-pinterest-via-playwright.md) |
| ADR-006 | Jobs Assíncronos em Threads com Estado em Memória e Polling                                                 | STUDIO     | Aceita  | [generated/STUDIO/ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md](./generated/STUDIO/ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md) |
| ADR-007 | Mood board de vibe única — um prompt, teto de 8 imagens selecionadas, grid de 4 como orientação de UI       | MOOD       | Aceito  | [generated/MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md](./generated/MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md) |
| ADR-008 | Estratégia de Testes sem Rede/Navegador, CI com Ruff+Pytest e Gitflow com Rastreabilidade Task-Id           | STUDIO     | Aceito  | [generated/STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md](./generated/STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md) |
| ADR-009 | Detecção de batidas com numpy + ffmpeg (sem librosa) | MUSIC | Aceito | [ADR-009](generated/MUSIC/ADR-009-deteccao-de-batidas-com-numpy-e-ffmpeg.md) |

## Grafo de relacionamentos

```mermaid
graph LR
    ADR001["ADR-001<br/>Monólito sem auth"]
    ADR002["ADR-002<br/>Higgsfield via CLI"]
    ADR003["ADR-003<br/>Persistência em arquivos"]
    ADR004["ADR-004<br/>Fidelidade ao roteiro"]
    ADR005["ADR-005<br/>Scraping Pinterest"]
    ADR006["ADR-006<br/>Jobs em threads"]
    ADR007["ADR-007<br/>Mood board vibe única"]
    ADR008["ADR-008<br/>Testes sem rede e CI"]

    ADR001 --- ADR003
    ADR001 --- ADR006
    ADR003 --- ADR006
    ADR002 --- ADR006
    ADR005 --- ADR006
    ADR002 --- ADR007
    ADR004 --- ADR002
    ADR004 --- ADR005
    ADR004 --- ADR007
    ADR008 --- ADR001
    ADR008 --- ADR002
    ADR008 --- ADR003
    ADR008 --- ADR004
    ADR008 --- ADR005
    ADR008 --- ADR006
    ADR008 --- ADR007
```

**Legenda dos agrupamentos:**
- **Backbone STUDIO** (ADR-001, ADR-003, ADR-006): a arquitetura base de processo único, sem
  banco de dados e com jobs em threads/memória é coerente e mutuamente referenciada.
- **CLI e scraping como execuções assíncronas** (ADR-002, ADR-005 → ADR-006): a chamada ao CLI
  da Higgsfield e o scraping do Pinterest são as duas operações de longa duração que o modelo de
  threads + polling do ADR-006 existe para suportar.
- **Guarda-chuva de fidelidade ao curso** (ADR-004 → ADR-002, ADR-005, ADR-007): o ADR-004 é a
  restrição arquitetural que justifica explicitamente as escolhas de CLI-only (ADR-002), scraping
  via Playwright (ADR-005) e vibe única (ADR-007).
- **Integração Higgsfield ↔ Mood board** (ADR-002 ↔ ADR-007): o mood board consome as imagens
  geradas/importadas via CLI da Higgsfield.
- **Testes e CI cobrem todo o domínio** (ADR-008 ↔ todas): a estratégia de testes sem rede/CI se
  aplica a STUDIO, HIGGSFIELD, REFS e MOOD por igual.
