# Potencial ADR: Integração com a Higgsfield somente via CLI oficial (nunca API HTTP direta, nunca automação de UI) — com modo UI de importação manual

**Módulo**: HIGGSFIELD
**Categoria**: Arquitetura
**Prioridade**: Must Document (Score: 150/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: não
**Data de identificação**: 2026-08-25

## Contexto

O `orquestrador-studio` precisa gerar imagens (e, em etapas futuras, vídeo/áudio) via Higgsfield
para todas as etapas do curso a partir da etapa 2 (mood board) em diante. A Higgsfield oferece
pelo menos três superfícies possíveis de integração: (1) a API HTTP `api.higgsfield.ai`
diretamente; (2) automação da interface web (scraping/RPA), e (3) o CLI oficial `@higgsfield/cli`
(binário `higgsfield`/`hf`, instalado via `npm i -g`, fora do `requirements.txt` Python do
projeto). O projeto foi criado (scaffold inicial) em 2026-08-25 e o módulo `studio/higgsfield.py`
existe desde o primeiro commit do repositório (`chore: scaffold inicial do Orquestrador Studio
(etapas 1 e 2)`, 2026-08-25 02:31:34 -0300) — ou seja, a decisão de usar apenas o CLI já nasceu
com o módulo, não foi uma migração posterior. O arquivo recebeu dois ajustes ainda no mesmo dia:
`feat: etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e Compozy` (02:39:46)
e, poucos minutos depois, `fix: ponte do CLI tolerante a timeout/binário ausente, estimativa de
custo antes de gerar, 404 uniforme para projeto inexistente` (02:43:39) — este último já reagindo
a um ponto frágil da própria decisão (o subprocess podia propagar `TimeoutExpired`/
`FileNotFoundError` não tratados). Por ser um projeto recém-criado, o histórico git ainda é raso
(mesmo dia), mas a decisão está documentada como regra irrevogável em três lugares independentes
e coerentes entre si: o docstring do próprio módulo (`studio/higgsfield.py:1-4`), o `CLAUDE.md`
da raiz (seção "Gates de fidelidade ao roteiro do curso") e o HLD do domínio
(`docs/domains/higgsfield/hld.md`).

A motivação de negócio vem da própria documentação oficial da Higgsfield, citada literalmente no
docstring do módulo: "nunca chamar `api.higgsfield.ai` direto; o CLI cuida de auth, upload e
polling." Adicionalmente, o plano de produto (`docs/plano/plano-higgsfield.md:6,312`) documenta
que o plano de assinatura do usuário pode oferecer geração "ilimitada/grátis" **somente na
interface web**, benefício que **não se aplica** ao CLI/MCP. Isso criou uma segunda decisão
correlata: em vez de automatizar essa UI para captar o benefício (o que violaria a regra de "nunca
automatizar a UI"), o Studio expõe um "modo UI" onde o **usuário gera manualmente** as imagens na
interface web da Higgsfield e o Studio apenas **importa** o resultado depois, via
`hf.history_images()` → `mood.import_history()` (`studio/mood/service.py:160-172`), que lista o
histórico de jobs do CLI (`generate list --image`) — histórico esse que, segundo o próprio
docstring de `history_images()`, "inclui o que foi gerado na UI, se o backend listar tudo"
(`studio/higgsfield.py:62-64`). Ou seja: a mesma chamada de CLI usada para consultar histórico
serve tanto para jobs disparados pelo próprio Studio quanto para jobs gerados manualmente pelo
usuário na UI, sem que o Studio jamais precise abrir um navegador ou simular cliques na
Higgsfield.

## Decisão

1. Toda comunicação do `orquestrador-studio` com a Higgsfield acontece **exclusivamente** via
   `subprocess`, invocando o binário `higgsfield`/`hf` do CLI oficial `@higgsfield/cli` sempre com
   a flag `--json` (`studio/higgsfield.py:_run`, linha 21-30). Não existe, em nenhum ponto do
   código, um cliente HTTP (`requests`/`httpx`/`urllib`) apontando para `api.higgsfield.ai`, nem
   dependência Python do tipo SDK oficial da Higgsfield.
2. É proibido automatizar a interface web da Higgsfield (scraping, RPA, Playwright etc. contra
   `higgsfield.ai`) para captar benefícios do plano do usuário (ex.: geração ilimitada). Essa
   proibição está registrada como regra irrevogável em `CLAUDE.md` ("Nunca chamar `api.higgsfield.ai`
   direto; nunca automatizar a UI da Higgsfield").
3. Para aproveitar geração ilimitada/gratuita disponível apenas na UI web, o **modo UI** é
   oferecido como fluxo alternativo: o próprio usuário gera as imagens manualmente na interface
   web da Higgsfield (fora do Studio, fora de qualquer automação), e o Studio apenas **importa**
   os resultados depois, lendo o histórico de jobs devolvido pelo próprio CLI
   (`hf.history_images()` → `mood.import_history()`). O Studio nunca dispara nem controla a
   sessão da UI.
4. Autenticação (OAuth via `higgsfield auth login`), upload de arquivos de referência e o
   *polling* de jobs assíncronos (potencialmente demorados, sobretudo para vídeo) ficam
   inteiramente delegados ao binário do CLI — o módulo Python não reimplementa nenhuma dessas
   responsabilidades.

## Alternativas Consideradas

- **Chamar `api.higgsfield.ai` diretamente via HTTP**: descartada explicitamente pela própria
  documentação oficial da Higgsfield, que instrui a não fazer isso e delega auth/upload/polling ao
  CLI. Reimplementar essas responsabilidades no Studio duplicaria lógica que o CLI já resolve e
  criaria uma dependência direta de um contrato de API não documentado para uso por terceiros.
- **Automatizar a interface web (scraping/RPA)** para aproveitar o benefício de geração
  ilimitada do plano do usuário: descartada e proibida por regra explícita — risco de violar
  termos de uso da Higgsfield e de quebrar a cada mudança de layout da UI (o mesmo tipo de risco
  já assumido conscientemente, com mitigações, para o Pinterest no módulo `REFS` — ver decisão
  potencial sobre Playwright/perfil persistente do Pinterest nesse módulo — mas que aqui foi
  deliberadamente **evitado**, não replicado, por se tratar do serviço pago que é o núcleo do
  produto).
- **Modo UI com automação (Playwright contra a Higgsfield)**: não adotado; em vez disso, o modo UI
  ficou puramente manual (o humano gera, o Studio só importa via CLI), evitando o mesmo risco de
  ToS que a automação da UI da Higgsfield traria.

## Consequências

### Positivas
- Autenticação, upload e *polling* de jobs assíncronos (que podem levar minutos, especialmente em
  vídeo) ficam inteiramente sob responsabilidade do CLI mantido pela própria Higgsfield — o Studio
  não precisa reimplementar OAuth, gestão de tokens de curta duração, nem lógica de retry de
  polling.
- Reduz superfície de risco de conta: nenhuma automação de UI que possa ser interpretada como
  abuso de termos de uso do plano "ilimitado".
- O modo UI aproveita o benefício de geração ilimitada do plano do usuário sem violar a proibição
  de automação — o humano decide quando e o que gerar manualmente, e o Studio só entra depois,
  na importação.
- Trocar de "Higgsfield UI" para "Higgsfield CLI" como execução primária da etapa é coerente com o
  gate 3 do `CLAUDE.md` ("Trocar ferramenta não é desvio; trocar processo é" — aula 005 do curso),
  já citado explicitamente como exemplo desse próprio gate.

### Negativas / Trade-offs
- Dependência total e sem alternativa de fallback do binário `@higgsfield/cli`: se o CLI mudar seu
  contrato de saída JSON, remover/renomear subcomandos, ou ficar indisponível, o Studio não tem
  nenhum caminho alternativo de comunicação com a Higgsfield (não há client HTTP de reserva).
  Esse risco é agravado pelo fato de o binário ser gerenciado via npm, **fora** do
  `requirements.txt`/`requirements-dev.txt` do projeto — nenhuma ferramenta de dependência Python
  o rastreia ou alerta sobre atualizações.
- O contrato de saída do CLI não é versionado nem tipado do ponto de vista do projeto, o que já
  obrigou o módulo a adotar parsing defensivo (achatamento de JSON + busca por sufixo de chave +
  regex de URL de imagem, em `_flatten`/`_pick`/`IMG_URL_RE`) em vez de um schema estrito — uma
  consequência direta e deliberada de não ter um SDK oficial tipado.
- O modo UI cria uma segunda via de entrada de dados no mood board (importação de histórico) que
  não distingue, no resultado, imagens geradas pelo próprio Studio das geradas manualmente pelo
  usuário na UI — ambas chegam pela mesma chamada `generate list --image`. Isso é aceitável para o
  propósito atual (aproveitar o plano ilimitado), mas significa que a proveniência exata de cada
  imagem importada não é rastreada separadamente.
- Qualquer mudança de versão do CLI que altere nomes de flags ou de campos do JSON só é percebida
  em tempo de execução (erro do subprocess ou campo ausente no parsing defensivo), não em tempo de
  build/CI, já que não há teste de contrato contra uma versão fixada do binário.

## Evidências no Código

### Arquivos-chave
- `studio/higgsfield.py` (linhas 1-4) — docstring do módulo declarando a regra: "Ponte fina com o
  CLI oficial da Higgsfield ... Regra da doc oficial: nunca chamar api.higgsfield.ai direto; o CLI
  cuida de auth, upload e polling."
- `studio/higgsfield.py` (linhas 13, 21-30) — `BIN = shutil.which("higgsfield") or shutil.which("hf")`
  e `_run()`, único ponto de saída do módulo para o mundo externo, sempre via
  `subprocess.run([BIN, *args, "--json"], ...)`.
- `studio/mood/service.py` (linhas 160-172) — `import_history()`, que chama `hf.history_images()`
  para trazer tanto jobs disparados pelo Studio quanto os gerados manualmente na UI (modo UI).
- `CLAUDE.md` (linhas 74-80, seção "Stack e arquitetura") — "Ponte com a Higgsfield **somente**
  via CLI oficial ... Nunca chamar `api.higgsfield.ai` direto; nunca automatizar a UI da
  Higgsfield."
- `docs/domains/higgsfield/hld.md` (linhas 1-11) — objetivo técnico do domínio, repetindo a regra
  e explicitando o motivo do modo UI: "Nunca automatizar a UI web (o ilimitado do plano é de uso
  humano na interface; burlar isso arrisca a conta)."
- `docs/plano/plano-higgsfield.md` (linhas 4-6, 312) — fonte da regra de negócio sobre o benefício
  "ilimitado/grátis da UI" não se aplicar ao CLI/MCP, e a recomendação de gerar imagens na UI
  quando o plano permitir.

### Trecho de código
```python
# studio/higgsfield.py:1-4
"""Ponte fina com o CLI oficial da Higgsfield (`higgsfield`), sempre via subprocess + --json.

Regra da doc oficial: nunca chamar api.higgsfield.ai direto; o CLI cuida de auth, upload e polling.
"""
```

```python
# studio/higgsfield.py:21-30
def _run(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    if not BIN:
        return 127, "", "higgsfield CLI não encontrado (npm i -g @higgsfield/cli)"
    try:
        p = subprocess.run([BIN, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"higgsfield {' '.join(args[:2])}: tempo esgotado após {timeout}s"
    except (FileNotFoundError, PermissionError) as e:
        return 127, "", f"higgsfield CLI indisponível: {e}"
    return p.returncode, p.stdout, p.stderr
```

```python
# studio/mood/service.py:160-163 (modo UI: import_history reaproveita o mesmo histórico do CLI)
def import_history(pid: str, size: int = 50) -> dict:
    """Importa imagens do histórico de jobs do CLI (`higgsfield generate list --image`)."""
    root = _project_root(pid)
    jobs = hf.history_images(size)
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:31:34 -0300 (commit `chore: scaffold inicial do Orquestrador
  Studio (etapas 1 e 2)`) — o módulo `studio/higgsfield.py` já nasceu com a regra "CLI-only" no
  docstring; não houve uma versão anterior chamando a API HTTP diretamente.
- Modificado: 2 commits adicionais, ainda no mesmo dia — `feat: etapa 2 alinhada à aula 009,
  testes, CI, gitflow, skills de projeto e Compozy` (02:39:46) e `fix: ponte do CLI tolerante a
  timeout/binário ausente, estimativa de custo antes de gerar, 404 uniforme para projeto
  inexistente` (02:43:39).
- Última mudança: 2026-08-25 02:43:39 -0300 — o tema do commit ("ponte do CLI tolerante a
  timeout/binário ausente") mostra a decisão sendo reforçada e endurecida (tratamento explícito de
  `subprocess.TimeoutExpired`/`FileNotFoundError`/`PermissionError` em `_run`), não questionada:
  o ajuste foi tornar a dependência do CLI mais resiliente a falhas, não substituí-la.
- Temas recorrentes: "CLI", "json", "timeout", "tolerante" — todos girando em torno de tornar a
  integração via subprocess mais robusta, nunca em torno de trocar de mecanismo de integração.
- Nota sobre profundidade do histórico: o repositório é recém-criado (todos os commits datados de
  2026-08-25); portanto a "estabilidade" desta decisão não pode ainda ser aferida por longevidade
  de commits, mas sim pelo fato de estar registrada como gate irrevogável em três documentos
  independentes (`CLAUDE.md`, HLD do domínio, docstring do módulo) desde a fundação do projeto.

## ADRs Relacionados / Potenciais

- Referencia, sem duplicar, a decisão transversal "Execução de jobs em background via threads"
  (cross-cutting concern documentado a partir do módulo `STUDIO`) — é essa infraestrutura de
  threads que envolve as chamadas bloqueantes de `hf.generate()` feitas por `mood/service.py`.
- Referencia, sem duplicar, a decisão potencial do módulo `REFS` sobre Playwright com perfil de
  navegador persistente para o Pinterest — mencionada aqui apenas como contraste: para a
  Higgsfield, a mesma categoria de risco (automação de UI de terceiros) foi resolvida de forma
  oposta (proibição total, com modo UI manual como alternativa), em vez de mitigada com
  automação "em ritmo humano".
- Relaciona-se com o gate "Fidelidade ao curso" (`CLAUDE.md`), citado no mapeamento como
  preocupação transversal a todos os módulos de domínio — em particular o item 3 desse gate
  ("Trocar ferramenta não é desvio; trocar processo é"), que usa exatamente a substituição de
  Higgsfield UI por Higgsfield CLI como exemplo do próprio gate.

## Notas Adicionais

- O relatório de análise profunda do componente (`docs/agents/component-deep-analyzer/
  component-analysis-Higgsfield-Bridge-2026-08-25_02-36-48.md`) aponta como risco Alto a ausência
  de checagem de saldo/orçamento antes de `generate()` cobrar créditos — isso não é parte da
  decisão "CLI-only" em si, mas é uma consequência prática dela: como toda a cobrança é opaca ao
  Studio (fica dentro do CLI/conta Higgsfield), o Studio não tem hoje nenhum mecanismo de bloqueio
  preventivo de gasto. Vale considerar registrar isso separadamente como item de acompanhamento
  técnico (não necessariamente uma ADR), já que `docs/plano/plano-higgsfield.md:47` menciona
  `budget_credits`/`costs.json` apenas como conceito de planejamento futuro, ainda não
  implementado.
- A função pública `cost()` do bridge (estimativa de créditos sem gastar) existe e é testável, mas
  não tem nenhum chamador hoje em `studio/app.py` nem no frontend — é funcionalidade pronta porém
  não integrada à UI. Não constitui uma decisão arquitetural própria, mas é um ponto a considerar
  ao formalizar esta ADR (se vale expor `cost()` na UI antes de liberar geração, como já sugerido
  no HLD do domínio em "Próximos passos").
- Author automation note: título e conteúdo deste arquivo foram gerados por análise de código;
  recomenda-se ao usuário (magnatadevs@gmail.com, autor do commit de scaffold) validar o texto
  final antes da formalização em `docs/adrs/generated/`, sobretudo os pontos de "Consequências
  Negativas", que descrevem riscos técnicos observados e não necessariamente aceitos como
  permanentes pela equipe.
