# ADR-031: Execução de skill do Claude CLI com escrita em disco, separada do bot de prompts

**Status:** Aceito
**Data:** 2026-09-02
**Task-Id:** ADH-OS-20260902-01
**ADRs relacionados:** [ADR-001 (monólito single-process, loopback)](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-003 (persistência em arquivos)](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004 (fidelidade ao roteiro do curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006 (jobs assíncronos em threads com polling)](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008 (testes sem rede)](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-013 (biblioteca global de mood boards)](./ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md), [ADR-016 (créditos e custos)](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-002 em `HIGGSFIELD/` (integração só via CLI oficial)](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md)

> Nota de citação: existem **três** arquivos `ADR-028` no repositório (um em `HIGGSFIELD/` e dois em
> `STUDIO/`). Toda referência a ADR neste documento vem com o diretório ou com link relativo
> resolvível — "ADR-028" solto é ambíguo aqui.

## Contexto e Problema

O Studio já conversa com o Claude por um caminho só: `studio/common/prompter.py`, o "bot de prompts"
do curso (aulas 007/009/012). Ele roda `claude -p` com a assinatura do usuário — nunca chave de API,
nunca `api.anthropic.com` direto — e foi desenhado para **uma pergunta curta que devolve JSON**:

```python
args = [BIN, "-p", prompt, "--model", MODEL, "--output-format", "text", "--max-turns", "6"]
if images:
    args += ["--allowedTools", "Read"]
```

Sem `cwd`, sem `Bash`, sem `Write`, seis turnos, `TIMEOUT_S = 180`. É uma ponte deliberadamente
estreita: o pior que uma resposta ruim faz é virar um prompt ruim na tela.

A cadeia de skills `mood_` (`mood_vibe_scout` → `mood_visual_dna` → `mood_board_builder`, orquestrada
por `mood_orquestrador`) é outra categoria de trabalho. Ela **lê** a foto escolhida, **roda script**
(Playwright no Pinterest), **baixa** dezenas de imagens de terceiros, **escreve** a prancha
`_moodboard.jpg`, o `dna.json`, o `leitura.md` e o `curadoria.md`, e **encadeia outras skills e
subagentes**. A corrida manual de referência (2026-09-02) levou ~15 minutos e 84 downloads.

Rodar isso pelo `prompter._run()` é impossível, e não por preferência de estilo — por quatro fatos:

1. **`cwd`.** Sem o diretório de trabalho na raiz do repositório, `.claude/skills` não resolve e a
   skill simplesmente não é encontrada.
2. **`--allowedTools`.** `Read` sozinho não escreve prancha nem roda o script de coleta.
3. **`--max-turns 6`.** Uma cadeia de quatro skills não cabe em seis turnos.
4. **Timeout.** 180 s contra uma corrida de ~15 min.

Havia ainda uma quinta questão, de acoplamento: o modelo do bot vem de `STUDIO_PROMPTER_MODEL`.
Se a corrida reusasse essa variável, trocar o modelo do bot de prompts trocaria, silenciosamente, o
modelo de um processo que escreve no disco.

O problema desta ADR, então: **como o Studio passa a executar uma skill que escreve, sem afrouxar a
ponte estreita que já existe e sem inventar uma segunda forma de falar com o modelo?**

## Decision Drivers

- Preservar `prompter.py` exatamente como está: ele é o caminho do curso e tem contrato de
  fidelidade (ADR-004). Alargar o `_run()` para caber a corrida alargaria também o bot de prompts.
- Manter a regra de que a ponte com o modelo é o **CLI local com a assinatura do usuário** — nunca
  chave de API (mesmo princípio que a ADR-002 aplica à Higgsfield: só o CLI oficial).
- Confinar a escrita. Um processo com `Write` e `Bash` solto na máquina é superfície nova; ela
  precisa de fronteira explícita.
- Não fingir progresso nem esconder falha: um subprocess bloqueante de 15 min tem de reportar fases
  reais e falhar com o motivo (ADR-006 para o transporte, guidelines §7.2 para o erro).
- Não gastar crédito. A cadeia `mood_` é gratuita e não toca a Higgsfield.
- Continuar testável sem rede e sem `claude` real (ADR-008).

## Decisão

**Criar um segundo modo de execução do Claude CLI, em módulo próprio
(`studio/common/skill_runner.py`), irmão do `prompter._run()` e nunca uma alteração dele.** Cinco
decisões concretas:

1. **Dois runners, não um generalizado.** `prompter.py` não é tocado. A duplicação entre os dois é
   deliberada e pequena (montar argv e chamar `subprocess.run`); o que difere é tudo o que importa —
   permissões, tempo de vida, diretório de trabalho e contrato de retorno. Um runner único
   parametrizado faria a pergunta curta somente-leitura herdar a superfície da corrida que escreve.

2. **Permissões explícitas e mínimas, validadas por spike.** O comando passa
   `--allowedTools Read,Bash,Write,WebSearch,WebFetch,Skill,Agent` como um único argumento, e
   **não** passa `--max-turns`. O conjunto saiu de um spike executado em 2026-09-02
   (`claude -p "/mood_orquestrador --gate auto --objetivo ambiente"`, exit 0, `SKILL.md` carregado),
   não de suposição. `cwd` é a raiz do repositório (`studio.config.ROOT`).

3. **Env próprias, com default fixo.** `STUDIO_SKILL_MODEL` (default `claude-opus-4-8`) e
   `STUDIO_SKILL_TIMEOUT_S` (default `1800`). **`STUDIO_PROMPTER_MODEL` não é lida por este módulo**
   — há teste específico para isso. Valor de modelo vazio omite `--model` e deixa o CLI usar o
   default do usuário.

4. **A escrita é confinada por `--saida`.** A tela nunca aceita `saida` no corpo da requisição: o
   servidor o impõe como `MOODBOARDS_DIR/<mbid>/mood_run`. Isso mantém a corrida dentro do diretório
   do board (ADR-013), faz `/mbfiles` já servir as pranchas sem montagem nova, e casa com a
   persistência em arquivos da ADR-003. `MOODBOARDS_DIR` é gitignored, e há teste executável
   (`git check-ignore`) garantindo que as imagens de terceiros não podem entrar no versionamento.

5. **O contrato de retorno é um arquivo, e a validação é de shape mínimo.** A skill grava
   `_run.json` na raiz do `--saida`; o runner o lê no fim e verifica apenas que é um objeto JSON e
   que, havendo `boards`, `boards` é lista. Validar o conteúdo quebraria a cada evolução da skill.
   Cada modo de falha é uma exceção nomeada — `SkillUnavailable`, `SkillTimeout`, `SkillFailed`,
   `SkillManifestMissing`, `SkillManifestInvalid` — e nenhuma delas é engolida em valor de retorno
   ambíguo.

**Decisão acessória, mas estruturante: o gate humano vira `auto` e a revisão muda de lugar.**
Em `claude -p` não existe `AskUserQuestion`, então o modo `interativo` das skills é inexecutável
não-interativamente. A tela sempre manda `--gate auto`. A revisão humana não desaparece: em modo
`auto` a skill grava `leitura.md` e `curadoria.md` por board, e a tela linka os dois no resultado.
Deixa de ser uma parada no meio da corrida e passa a ser uma leitura depois dela.

**A corrida é gratuita.** Nada neste caminho importa `studio/higgsfield.py`, chama `require_cli()`
ou registra `spend_action`/`record_generation` (ADR-016, e ADR-002 em `HIGGSFIELD/`). A confirmação
que a tela pede antes de disparar **não é de custo**: é do volume de downloads de terceiros
(`downloads = objetivos × (board − 1) × n`).

## Consequências

**Positivas**

- `prompter.py` fica com zero linhas de diff: a ponte estreita do bot de prompts continua estreita.
- O runner é genérico. Qualquer feature futura que precise rodar uma skill do Claude Code com
  escrita em disco usa `run_skill()` sem reabrir esta decisão.
- A superfície nova tem fronteira nomeada e testável: `cwd` fixo, tools enumeradas, `--saida`
  imposto pelo servidor, destino gitignored.
- Trocar o modelo do bot de prompts deixa de poder trocar o modelo da corrida.

**Negativas / custos**

- **Superfície ampliada, e isso é real.** Um subprocess com `Bash` e `Write` pode, em princípio,
  escrever fora do `--saida`: o confinamento vem do parâmetro e do comportamento da skill, não de
  um sandbox do sistema operacional. O que a decisão garante é que *o Studio* nunca passa um destino
  arbitrário, e que o destino que ele passa é gitignored.
- **O CI nunca exercita a corrida real** (ADR-008): os testes usam um fake do CLI. A corrida ponta a
  ponta é validação manual, registrada na PR. Uma regressão que só apareça com `claude` de verdade
  não é pega pela suíte.
- **O `_run.json` é contrato de produtor externo.** Uma mudança de formato na skill vira falha em
  tempo de execução (`SkillManifestInvalid`), não erro de compilação. Aceito conscientemente: a
  alternativa — validar o conteúdo inteiro — quebraria a cada versão da skill.
- **A revisão humana virou pós-fato.** Em `--gate auto` a skill decide sozinha as três paradas e
  registra em arquivo. Quem quiser vetar uma curadoria só descobre depois de os downloads terem
  acontecido. É o preço de a tela poder disparar a cadeia; o mitigador é a estimativa obrigatória
  antes do POST.
- **Duplicação controlada entre os dois runners.** Se um terceiro modo de chamada aparecer, esta
  decisão deve ser revisitada — três cópias de "montar argv e chamar o CLI" passariam a pedir uma
  base comum.

**Escopo de fidelidade (ADR-004).** A cadeia `mood_` inteira é `[extensão]`: a aula 009 ensina UM
mood de vibe única por campanha e não ensina pesquisa de referência no Pinterest. Está marcada como
tal no código e na documentação, e não altera nada do que a etapa 2 faz.
