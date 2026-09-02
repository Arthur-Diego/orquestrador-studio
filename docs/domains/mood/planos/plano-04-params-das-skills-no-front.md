# Plano 04 — Expor os parâmetros das skills ao frontend

Task-Id: `ADH-OS-20260902-04`
Status: **plano** — nada implementado.
Data: 2026-09-02 (escopo reduzido na mesma data — ver §2)

---

## 1. O que se quer

Controlar as skills `mood_` pela tela, com **dois botões e nada além disso**:

- **gate humano ligado ou desligado** — `interativo` (a skill para e pergunta) ou `auto`
  (ela decide, registra em arquivo e vai até o fim);
- **quais objetivos gerar** — um, vários ou todos os quatro.

E, quando o usuário não escolhe nada, tudo cai no default da skill.

## 2. O que este plano **não** faz mais (decisão de 2026-09-02)

Uma versão anterior deste plano propunha um vocabulário de restrição de busca
(`--assunto`, `--tipo`, `--excluir`, `--orientacao`, `--min-lado`, `--max-termos`, `--modo`,
`--funcoes`) espalhado pelas três skills. **Foi retirado a pedido do usuário**: a qualidade da
consulta é responsabilidade da skill, não da tela.

Consequências, já aplicadas nos `SKILL.md`:

- `mood_orquestrador` e `mood_board_builder` voltaram a ter só os parâmetros de **estrutura**
  (`--objetivo`, `--gate`, `--board`, `--n`, `--saida`, `--fundo`, `--params`);
- a `mood_vibe_scout` não ganha parâmetro novo nenhum.

### Sobre restringir o assunto: o scout já faz isso

A `mood_vibe_scout` recebe uma **descrição livre da campanha** como argumento posicional —
`"perfume masculino, público 25-40, quero algo escuro"` — que é lida antes da entrevista e
desativa as perguntas já respondidas. Some-se a entrevista de diretor de arte e o `--vibes`
(slugs garantidos na shortlist), e o assunto **já está restringido** por esse caminho. Um
`--assunto` seria um segundo jeito de dizer a mesma coisa.

Onde o lixo apareceu de fato não foi no scout: foram duas consultas da
`mood_board_builder` na corrida de 2026-09-02. O tratamento disso continua sendo o que a skill
já manda fazer — refazer a consulta **uma vez** e, na segunda falha, seguir sem ela — e não
vira parâmetro de tela.

## 3. O buraco

Se a tela tiver os campos hardcoded, cada parâmetro novo nas skills exige mexer no front, e as
duas verdades divergem em silêncio. O antídoto é a tela **perguntar** à API quais parâmetros
existem.

## 4. O contrato

```
GET /api/skills/mood/params
```

```json
{
  "mood_orquestrador": {
    "objetivo": {"tipo": "multi",  "default": [], "obrigatorio_em_auto": true,
                 "opcoes": ["ambiente", "campanha", "produto", "personagem"],
                 "rotulo": "Objetivos", "ajuda": "um board por objetivo marcado"},
    "gate":     {"tipo": "enum",   "default": "interativo",
                 "opcoes": ["interativo", "auto"],
                 "rotulo": "Aprovação humana",
                 "ajuda": "auto = a skill decide sozinha e registra em arquivo"},
    "board":    {"tipo": "inteiro","default": 8, "min": 4, "grupo": "avancado"},
    "n":        {"tipo": "inteiro","default": 3, "min": 1, "grupo": "avancado"},
    "fundo":    {"tipo": "enum",   "default": "escuro",
                 "opcoes": ["escuro", "claro"], "grupo": "avancado"}
  },
  "mood_vibe_scout": {
    "descricao": {"tipo": "texto",  "default": "", "rotulo": "Sobre a campanha",
                  "ajuda": "o que você já sabe; é lido antes da entrevista"},
    "vibes":     {"tipo": "lista",  "default": [], "grupo": "avancado"},
    "n":         {"tipo": "inteiro","default": 3, "min": 1, "max": 8, "grupo": "avancado"}
  }
}
```

Duas regras que fazem "controle total" e "modo default" serem o mesmo caminho de código:

- **campo vazio não é enviado** — a skill cai no default dela;
- **o front não conhece nenhum campo que não venha daqui.**

`obrigatorio_em_auto` existe porque, com `--gate auto`, a skill não tem como perguntar: foto e
objetivo precisam vir preenchidos, senão ela para e diz o que falta.

## 5. Escopo

### Entra
- `GET /api/skills/mood/params` em `studio/moodboards/router.py`, servindo o manifesto.
- Um teste que **falha se o manifesto e os `SKILL.md` divergirem** — é o que impede as duas
  verdades de se separarem.
- Front (`studio/web/moodboards.js`): formulário gerado do manifesto. `Objetivos` e
  `Aprovação humana` visíveis; o grupo `avancado` recolhido.
- Atualizar `docs/domains/mood/skills-mood-uso.md`.

### Não entra
- Vocabulário de restrição de busca (ver §2).
- Qualquer campo hardcoded no front.
- Mudar o comportamento das skills — elas já aceitam `--objetivo` e `--gate`.

## 6. Passos

1. Definir o manifesto (§4) — é contrato de UI, mudar depois dói.
2. Endpoint + teste de divergência manifesto ↔ `SKILL.md`.
3. Front: formulário do manifesto, com "avançado" recolhido.
4. Atualizar o guia.
5. `make verify` + PR pelo gate `ft-pr`.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Manifesto e skill divergirem | teste de divergência (passo 2) |
| Usuário marcar `todos` sem ver o custo | a estimativa de downloads é do Plano 01, que é quem dispara |
| `auto` sem foto ou sem objetivo | `obrigatorio_em_auto` no manifesto + a skill já para e diz o que falta |

## 8. Critérios de aceite

- A tela mostra exatamente dois controles principais: **objetivos** (múltipla escolha, com
  "todos") e **aprovação humana** (interativo/auto).
- Nada preenchido = comportamento default das skills.
- `GET /api/skills/mood/params` reflete os parâmetros reais; o teste falha se divergirem.
- Nenhum campo do formulário existe fora do manifesto.
- `make verify` verde.
