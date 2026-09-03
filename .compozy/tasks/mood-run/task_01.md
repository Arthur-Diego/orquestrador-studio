---
status: completed
title: Runner de skill do Claude CLI com escrita em disco (`skill_runner`)
type: backend
complexity: medium
---

# Task 1: Runner de skill do Claude CLI com escrita em disco (`skill_runner`)

## Overview

Entrega `studio/common/skill_runner.py`, o **irmão** de `prompter._run()`: mesmo binário
(`claude -p`, assinatura do usuário, sem chave de API), modo de execução diferente — `cwd` na raiz
do repositório, `--allowedTools` explícito com escrita e busca, sem teto de turnos, timeout de
minutos e leitura de um contrato de saída em arquivo (`_run.json`). Todas as demais tasks da
feature consomem este módulo; ele é a fatia que o ADR-031 registra.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** O módulo MUST ser **novo**. `studio/common/prompter.py` MUST NOT ser alterado em
  nenhuma linha — nem para extrair helper comum. Duplicação controlada aqui é decisão registrada
  (ADR-031): o runner de pergunta curta somente-leitura e o runner de corrida com escrita têm
  ciclos de vida diferentes.
- **R2.** `BIN` MUST ser um símbolo de módulo (`shutil.which("claude")`), monkeypatchável — é o
  que torna os testes possíveis sem `claude` real (padrão de `prompter.BIN`, seção D do recon).
- **R3.** `MODEL` MUST vir de `STUDIO_SKILL_MODEL` (default `"claude-opus-4-8"`) e
  `TIMEOUT_S` de `STUDIO_SKILL_TIMEOUT_S` (default `1800`). O módulo MUST NOT ler
  `STUDIO_PROMPTER_MODEL` — trocar o modelo do bot de prompts não pode trocar o da corrida.
  `MODEL` vazio (`""`) MUST omitir `--model` do comando, deixando o CLI usar o default do usuário.
- **R4.** O comando MUST conter `--allowedTools` com o conjunto do spike D2, como **um único
  argumento separado por vírgula**: `Read,Bash,Write,WebSearch,WebFetch,Skill,Agent`. MUST NOT
  conter `--max-turns`: uma cadeia de quatro skills não cabe nos 6 turnos do prompter.
- **R5.** `subprocess.run` MUST receber `cwd=<raiz do repo>` (`studio.config.ROOT`). Sem isso
  `.claude/skills` não resolve e a skill não é encontrada.
- **R6.** `build_prompt(skill, flags)` MUST montar `/<skill> --flag valor …`, omitindo chaves cujo
  valor seja `None`, e MUST envolver valores de caminho em aspas duplas. MUST levantar
  `ValueError` quando qualquer valor contiver `"` (o prompt é uma string única; aspas quebrariam
  a citação) — caso E12 da matriz de erros.
- **R7.** Os modos de falha MUST ser exceções distintas e nomeadas, nunca valor de retorno
  ambíguo (guideline §7.2): `SkillUnavailable` (CLI ausente, E1), `SkillTimeout` (E2),
  `SkillFailed` (returncode != 0, E3), `SkillManifestMissing` (E4), `SkillManifestInvalid` (E5).
  As três últimas MUST herdar de `SkillFailed`. MUST NOT existir nenhum
  `except Exception: return {}` no módulo.
- **R8.** A validação do `_run.json` MUST ser de **shape mínimo** — é um objeto JSON e, se tiver
  `boards`, `boards` é lista. MUST NOT validar o conteúdo dos boards: o arquivo é de um produtor
  externo que evolui, e validar demais quebraria a cada versão da skill.
- **R9.** Em falha, a **cauda** do `stdout`/`stderr` (no máximo 20 linhas / 4000 caracteres) MUST
  compor a mensagem ou o log. Saída inteira de uma corrida de 15 min não cabe num job dict.
- **R10.** Todo o código novo MUST ser anotado (guidelines §6/§7), com `Raises:` no docstring de
  cada função que levanta, e MUST passar `ruff check` com `line-length=120`.
- **R11.** O módulo MUST NOT importar `studio.higgsfield`, MUST NOT chamar
  `settings.record_generation` e MUST NOT registrar `spend_action`: a cadeia `mood_` é gratuita
  (ADR-016) e não toca Higgsfield (ADR-002).
</requirements>

## Subtasks
- [x] 1.1 Criar `studio/common/skill_runner.py` com o docstring de módulo explicando por que ele
      não é uma alteração do `prompter._run()` (as seis diferenças da tabela 5.6 do `_techspec.md`).
- [x] 1.2 Declarar as constantes de módulo (`BIN`, `MODEL`, `TIMEOUT_S`, `ALLOWED_TOOLS`,
      `RUN_MANIFEST`, limites de log) e a hierarquia de exceções.
- [x] 1.3 Implementar `available()` e `build_command()`.
- [x] 1.4 Implementar `build_prompt()` com a citação de valores e a recusa de aspas duplas.
- [x] 1.5 Implementar `run_skill()`: execução com `cwd`/timeout, classificação das falhas, leitura
      e validação do `_run.json`, e retorno do value object `SkillRun`.
- [x] 1.6 Escrever `tests/test_skill_runner.py` com o fake do CLI por duplo monkeypatch
      (`skill_runner.BIN` **e** `skill_runner.subprocess.run`), no padrão de `tests/test_prompter.py`.
- [x] 1.7 Cobrir a leitura de env própria recarregando o módulo com as duas variáveis setadas em
      valores diferentes.
- [x] 1.8 Rodar `ruff check studio tests` e a suíte nova.

## Implementation Details

Criar apenas `studio/common/skill_runner.py` e `tests/test_skill_runner.py`. A API pública está
literal na seção **5.6** do `_techspec.md`; a matriz de erros, na seção **6**; o formato do
`_run.json`, na seção **5.0** e na seção H do `recon-wave-10.md`.

O fake do CLI é uma função que substitui `subprocess.run`, registra os `args`/`kwargs` recebidos e
escreve o `_run.json` (e a prancha) no `--saida` antes de devolver um `CompletedProcess`. É assim
que os testes exercitam o caminho feliz sem rede e sem `claude` real (ADR-008).

### Relevant Files
- `studio/common/prompter.py` — o irmão a espelhar (`_run` nas linhas 284-298); **leitura apenas**.
- `studio/config.py` — `ROOT` (linha 5), o `cwd` do subprocess; **leitura apenas**.
- `tests/test_prompter.py` — o padrão de fake do CLI a copiar (linhas 10-27, 46-61).
- `docs/guidelines/python-development-guidelines.md` — §6 tipos, §7.1 assinaturas, §7.2 erros.

### Dependent Files
- `studio/moodboards/mood_run.py` (task_02) — único consumidor imediato.
- `docs/adrs/generated/STUDIO/ADR-031-…md` (task_04) — registra a decisão que este módulo encarna.

### Related ADRs
- **ADR-006** (jobs assíncronos) — o runner é chamado de dentro de uma thread de job.
- **ADR-008** (testes sem rede) — obriga o fake do CLI.
- **ADR-016** (créditos) — a cadeia é gratuita: nada de `spend_action`.
- **ADR-031** (a criar na task_04) — o modo de execução com escrita que este módulo implementa.

## Deliverables
- `studio/common/skill_runner.py` anotado, com docstrings Google-style e `Raises:`.
- `tests/test_skill_runner.py` verde, sem rede e sem `claude` real.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Casos inline (não há `_tests.md` neste fluxo — ver `_tasks.md`).

- [x] **UT-01** `BIN = None` → `available()` devolve `False`.
- [x] **UT-02** `build_command("/x")` devolve argv com `BIN`, `-p`, o prompt, `--output-format text`
      e `--allowedTools "Read,Bash,Write,WebSearch,WebFetch,Skill,Agent"`; `"--max-turns"` **não**
      está no argv.
- [x] **UT-03** com `MODEL = ""`, `build_command` **não** contém `--model`; com `MODEL = "m"`,
      contém `["--model", "m"]`.
- [x] **UT-04** `build_prompt("mood_orquestrador", {"foto": "/a/b.jpg", "objetivo": "ambiente",
      "gate": "auto", "board": 8, "n": 3, "fundo": None})` devolve
      `/mood_orquestrador --foto "/a/b.jpg" --objetivo ambiente --gate auto --board 8 --n 3` —
      chave com valor `None` omitida, caminho entre aspas.
- [x] **UT-05** `build_prompt` com um valor contendo `"` levanta `ValueError` (E12).
- [x] **UT-06** `run_skill` chama `subprocess.run` com `cwd == studio.config.ROOT` e
      `timeout == timeout_s`.
- [x] **UT-07** `BIN = None` → `run_skill` levanta `SkillUnavailable` (E1).
- [x] **UT-08** fake levanta `subprocess.TimeoutExpired` → `SkillTimeout`, e a mensagem contém o
      número de segundos do limite (E2).
- [x] **UT-09** fake devolve `returncode=1` com `stderr="boom"` → `SkillFailed` cuja mensagem
      contém `boom` (E3).
- [x] **UT-10** fake devolve `returncode=0` sem escrever `_run.json` → `SkillManifestMissing`, e a
      mensagem contém o caminho de `saida` (E4).
- [x] **UT-11** `_run.json` com texto não-JSON → `SkillManifestInvalid` (E5).
- [x] **UT-12** `_run.json` contendo uma lista JSON (não objeto) → `SkillManifestInvalid` (E5).
- [x] **UT-13** `_run.json` com `"boards": "x"` (não lista) → `SkillManifestInvalid` (E5).
- [x] **UT-14** caminho feliz: fake escreve `_run.json` com um board → `SkillRun.manifesto` traz o
      conteúdo, `seconds` é float ≥ 0 e `log` contém a cauda do stdout.
- [x] **UT-15** com `STUDIO_SKILL_MODEL="skill-m"` e `STUDIO_PROMPTER_MODEL="prompt-m"`, o módulo
      recarregado tem `MODEL == "skill-m"` (A9 do `_techspec.md`).
- [x] **UT-16** sem `STUDIO_SKILL_TIMEOUT_S`, `TIMEOUT_S == 1800`; com `"60"`, `TIMEOUT_S == 60`.

## Success Criteria
- Every assigned test case implemented and passing.
- `ruff check studio tests scripts` sem erro novo.
- `studio/common/prompter.py` com **zero** linhas de diff.
- Nenhum teste da suíte toca a rede nem executa `claude` de verdade.
- O diff da task não contém nenhum caminho sob `studio/web/`.
