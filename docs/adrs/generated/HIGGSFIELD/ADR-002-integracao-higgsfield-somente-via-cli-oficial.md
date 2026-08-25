# ADR-002: Integração com a Higgsfield somente via CLI oficial (nunca API HTTP direta ou automação de UI)

**Status:** Aceito
**Data:** 2026-08-25
**ADRs relacionados:** [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](../STUDIO/ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-007](../MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md), [ADR-008](../STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md)

## Contexto e Problema

O `orquestrador-studio` precisa gerar imagens (e, em etapas futuras, vídeo/áudio) via Higgsfield
para todas as etapas do curso a partir da etapa 2 (mood board) em diante. A Higgsfield oferece três
superfícies possíveis de integração: a API HTTP `api.higgsfield.ai` diretamente, automação da
interface web (scraping/RPA) e o CLI oficial `@higgsfield/cli` (binário `higgsfield`/`hf`,
instalado via `npm i -g`, fora do `requirements.txt` Python do projeto). O módulo
`studio/higgsfield.py` existe desde o primeiro commit do repositório (scaffold inicial,
2026-08-25) já com a regra "CLI-only" no docstring — não houve uma versão anterior chamando a API
HTTP diretamente. A decisão está registrada como regra irrevogável em três lugares independentes e
coerentes entre si: o docstring do próprio módulo, o `CLAUDE.md` da raiz e o HLD do domínio.

A motivação de negócio vem da própria documentação oficial da Higgsfield: nunca chamar
`api.higgsfield.ai` direto, pois o CLI cuida de auth, upload e polling. Adicionalmente, o plano de
produto documenta que o plano de assinatura do usuário pode oferecer geração "ilimitada/grátis"
somente na interface web, benefício que não se aplica ao CLI/MCP. Isso cria uma tensão: como
aproveitar esse benefício sem violar a proibição de automatizar a UI para captá-lo.

Uma preocupação adicional, não bloqueante para a decisão em si, é que o contrato de saída do CLI
(nomes de flags, IDs de modelo, campos JSON) não é versionado nem tipado do ponto de vista do
projeto e pode mudar entre versões do binário.

## Fatores da Decisão

- A documentação oficial da Higgsfield proíbe chamar `api.higgsfield.ai` diretamente e delega
  autenticação, upload e polling ao CLI.
- Automação da interface web (scraping/RPA) para captar o benefício de geração ilimitada do plano
  arrisca violar termos de uso e é frágil a qualquer mudança de layout da Higgsfield.
- Autenticação OAuth, upload de arquivos de referência e polling de jobs assíncronos (que podem
  levar minutos, sobretudo em vídeo) já são resolvidos pelo CLI mantido pela própria Higgsfield.
- O plano de assinatura do usuário oferece geração ilimitada/gratuita apenas na UI web, benefício
  que não se aplica ao CLI/MCP.
- O gate de fidelidade ao processo do curso (`CLAUDE.md`) permite trocar de ferramenta (UI por
  CLI) desde que a etapa produza o mesmo resultado — trocar processo é que não é permitido.

## Opções Consideradas

- CLI oficial `@higgsfield/cli` via `subprocess` (escolhida)
- API HTTP direta (`api.higgsfield.ai`)
- Automação da interface web (scraping/RPA/Playwright)

## Decisão

Opção escolhida: CLI oficial `@higgsfield/cli`, porque é a via endossada pela documentação oficial
da Higgsfield, delega auth/upload/polling ao binário mantido pela própria empresa, e viabiliza um
"modo UI" de importação manual sem violar a proibição de automação — o usuário gera manualmente as
imagens na interface web (para aproveitar o benefício de geração ilimitada do plano) e o Studio
apenas importa os resultados depois, lendo o histórico de jobs devolvido pelo próprio CLI
(`hf.history_images()` → `mood.import_history()`). O Studio nunca dispara nem controla a sessão da
UI.

A versão testada do CLI é `@higgsfield/cli` 1.1.23 (instalação global via npm), registrada no HLD
do domínio e nesta ADR. Como o catálogo de modelos e o contrato de flags/campos JSON podem mudar
entre versões do CLI, o projeto não fixa IDs de modelo no código: em vez disso, consulta o catálogo
vivo (`higgsfield model list --json`) em tempo de bootstrap e registra a versão testada do CLI como
referência de compatibilidade conhecida, não como trava de versão.

## Prós e Contras das Opções

### CLI oficial `@higgsfield/cli` (escolhida)

- Auth, upload e polling de jobs assíncronos ficam sob responsabilidade do CLI mantido pela
  Higgsfield, sem reimplementação no Studio.
- Reduz superfície de risco de conta: nenhuma automação de UI que possa ser interpretada como
  abuso de termos de uso do plano.
- O modo UI aproveita o benefício de geração ilimitada do plano sem violar a proibição de
  automação — o humano decide o que gerar, o Studio só importa depois.
- Dependência total do binário, gerenciado via npm, fora do `requirements.txt`/`requirements-dev.txt`
  Python — nenhuma ferramenta de dependência Python o rastreia.
- Contrato de saída não é versionado/tipado, exigindo parsing defensivo (achatamento de JSON +
  regex) em vez de um schema estrito.

### API HTTP direta (`api.higgsfield.ai`)

- Removeria a dependência de um binário externo gerenciado fora do gerenciador de pacotes Python
  do projeto.
- Contraria explicitamente a documentação oficial da Higgsfield.
- Exigiria reimplementar no Studio auth, upload e polling que o CLI já resolve.
- Depende de um contrato de API não documentado para uso por terceiros.

### Automação da interface web (scraping/RPA/Playwright)

- Captaria diretamente o benefício de geração ilimitada do plano, sem depender de um fluxo manual
  do usuário.
- Risco de violar termos de uso da Higgsfield ao automatizar o plano "ilimitado" de uso humano.
- Frágil a qualquer mudança de layout da interface web da Higgsfield.
- Proibida explicitamente por regra irrevogável do projeto (`CLAUDE.md`).

## Consequências

O Studio fica sem caminho alternativo de comunicação com a Higgsfield: se o CLI mudar seu contrato
de saída JSON, remover/renomear subcomandos, ou ficar indisponível, não há client HTTP de reserva.
Esse risco é mitigado, não eliminado, por registrar a versão testada (1.1.23) no HLD/README e por
consultar `higgsfield model list --json` no bootstrap em vez de fixar IDs de modelo no código —
ainda assim, mudanças de contrato só são percebidas em tempo de execução (erro de subprocess ou
campo ausente no parsing defensivo), não em tempo de build/CI.

O modo UI cria uma segunda via de entrada de dados no mood board (importação de histórico) que não
distingue, no resultado, imagens geradas pelo próprio Studio das geradas manualmente pelo usuário
na UI — ambas chegam pela mesma chamada de listagem de histórico do CLI. Isso é aceitável para o
propósito atual (aproveitar o plano ilimitado da UI sem automação), mas significa que a proveniência
exata de cada imagem importada não é rastreada separadamente.

A ausência de checagem de saldo/orçamento antes de gerar (cobrança de créditos fica opaca ao
Studio, dentro do CLI/conta Higgsfield) e a falta de exposição da função de estimativa de custo na
UI são consequências práticas da opacidade do CLI, mas não fazem parte do escopo desta decisão.

## Referências

- `studio/higgsfield.py:1-4`
- `studio/higgsfield.py:13,21-30`
- `studio/mood/service.py:160-172`
- `docs/domains/higgsfield/hld.md:1-19`
- `docs/plano/plano-higgsfield.md:4-6,312`
