# ADR-007: Mood board de vibe única — um prompt, teto de 8 imagens selecionadas, grid de 4 como orientação de UI
**Status:** Aceito
**Data:** 2026-08-25

## Contexto e Problema

A Etapa 2 do curso "O Orquestrador" (aula 009) define o mood board como **uma vibe só**: um
prompt único de ambiente/luz/cor — sem produto, sem pessoas, sem texto — que o usuário gera
como um grid de 4 imagens na UI web da Higgsfield, escolhendo depois até 8 imagens do mesmo
mood para compor a paleta e a documentação da campanha. O módulo `MOOD` precisava decidir como
reproduzir essa regra sem se transformar num mood board livre (múltiplos prompts por
categoria/tema, geração ilimitada de candidatas), padrão comum em outras ferramentas de
moodboarding mas não é o que a aula ensina.

Essa não é uma decisão implícita: o `CLAUDE.md` do repositório cita esta correção como o
exemplo canônico dos "Gates de fidelidade ao roteiro do curso": a etapa 2 foi corrigida de "6
tipos de prompt" para "1 prompt de vibe × grid de 4". O histórico git confirma a origem: o
módulo nasceu já com essa forma no commit de scaffold inicial, foi reforçado explicitamente no
commit seguinte (que nomeia o realinhamento à aula 009) e depois protegido por um terceiro
commit que endureceu a ordem de validação do teto de 8 imagens em `select()` (a checagem de
limite passou a rodar antes de qualquer efeito colateral em disco, evitando apagar a seleção
anterior em uma tentativa inválida).

O escopo desta decisão cobre exatamente o que o backend impõe — um único prompt de saída e um
teto rígido de 8 imagens selecionadas — e trata separadamente o "grid de 4", que é apenas uma
instrução textual (`ui_hint`) exibida ao usuário para ser seguida manualmente na UI externa da
Higgsfield; o Studio não gera nem valida esse grid.

## Decision Drivers

- Fidelidade ao roteiro do curso é o valor central do produto: a aula 009 ensina explicitamente uma vibe só, não múltiplos prompts por categoria.
- Necessidade de um contrato de API simples e previsível para `suggest_prompts`, sem lidar com N prompts paralelos ou seleção por categoria.
- Os artefatos de saída (`mood/selected/`, `palette.json`, `mood.md`) alimentam a Etapa 3 (imagem base) e precisam representar uma única direção de arte coesa.
- Prevenção de regressão: a regra de negócio precisa de um mecanismo de defesa (teste automatizado) contra reintrodução silenciosa de "múltiplos prompts".
- A geração de imagens em si ocorre fora do Studio (UI web da Higgsfield), então o número de imagens do grid não é um parâmetro que o backend pode tecnicamente impor sem integração adicional.

## Considered Options

1. **Vibe única com teto de seleção (opção escolhida)**: um prompt por chamada, variações limitadas a estilização, seleção final limitada a 8 imagens, com o "grid de 4" comunicado apenas como orientação textual ao usuário.
2. **Múltiplos prompts / categorias de vibe** (ex.: "6 tipos de prompt", um para cor, outro para textura, outro para iluminação): implementada primeiro no histórico do projeto e depois revertida por não corresponder ao que a aula 009 ensina.
3. **Seleção sem teto ou configurável**: tecnicamente trivial (bastaria remover a condição de limite em `select`), mas rejeitada por descaracterizar o conceito de "vibe única" da aula.

## Decision Outcome

Opção escolhida: **Vibe única com teto de seleção**, porque é a única que reproduz fielmente a
Etapa 2 conforme ensinada na aula 009 — um prompt de ambiente/luz/cor sem produto, pessoas ou
texto, com até 8 imagens selecionadas do mesmo mood. A variação (`variation`, 0–3) troca apenas
o tratamento estilístico do texto, nunca o conteúdo semântico do prompt, e é aplicada em módulo
circular, então não existe um número fixo de variações a esgotar. O teto de 8 é validado por
código em `select()` antes de qualquer escrita em disco; o "grid de 4" permanece como confiança
no usuário seguir a orientação (`ui_hint`) na UI externa da Higgsfield, já que o Studio não
participa da geração feita ali e não tem como contar ou impor esse número.

## Pros and Cons of the Options

### Vibe única com teto de seleção (escolhida)
- Boa, porque mantém fidelidade ao método do curso, que é o critério central de aceitação do produto.
- Boa, porque simplifica o contrato de `suggest_prompts` (sempre um item em `prompts[]`) e a UI correspondente.
- Boa, porque mantém os artefatos de saída pequenos e coerentes com uma única direção de arte para a Etapa 3.
- Má, porque limita deliberadamente o produto: explorar múltiplas vibes na mesma campanha exige repetir o fluxo da Etapa 2 mais de uma vez.

### Múltiplos prompts / categorias de vibe
- Boa, porque é um padrão comum em ferramentas de moodboarding e permitiria explorar mais eixos (cor, textura, iluminação) numa única passada.
- Má, porque diverge do que a aula 009 ensina, contrariando o gate de fidelidade do produto.
- Má, porque complica o contrato de API e a UI (N prompts paralelos, seleção por categoria).

### Seleção sem teto ou configurável
- Boa, porque é tecnicamente trivial de implementar.
- Má, porque uma seleção com dezenas de imagens deixa de comunicar uma direção de arte coesa, descaracterizando a "vibe única" da aula.
- Má, porque não há evidência de que esse comportamento tenha sido considerado necessário pelo curso.

## Consequences

A regra é protegida por teste automatizado explícito que falha citando a aula 009 caso a
invariante de prompt único seja quebrada, o que reduz o risco de regressão silenciosa. Em
contrapartida, o teto de 8 é validado **somente no backend**: o frontend não impede o usuário
de marcar mais de 8 candidatas antes de enviar a seleção, e o único feedback é o erro HTTP da
API — uma lacuna de UX decorrente diretamente desta decisão de negócio. O "grid de 4" não é
verificado nem contado pelo Studio em nenhuma camada; se o usuário gerar um número diferente de
imagens na UI da Higgsfield, nada no sistema detecta ou impede isso, apenas o teto de seleção
final (8) é tecnicamente imposto.

Os números "8" e "4" existem como literais inline no serviço, sem constante nomeada — qualquer
alteração futura de fidelidade ao curso (por exemplo, se uma revisão da aula mudar esses
números) exige localizar e alterar esse literal, sem um único ponto de configuração.

## References

- `studio/mood/service.py:68-91` — `suggest_prompts`: monta e retorna sempre um único item em `prompts[]`, com `ui_hint` orientando o grid de 4.
- `studio/mood/service.py:236-262` — `select`: valida `len(chosen) > 8` antes de qualquer escrita em disco.
- `tests/test_mood_service.py:69-80` — teste que assevera erro ao tentar selecionar mais de 8 imagens.
- `docs/domains/mood/hld.md:9-14,35-36` — HLD do domínio, registrando a mesma regra como padrão adotado.
- `CLAUDE.md:7-36` — gate de fidelidade ao roteiro do curso, citando esta correção como exemplo.
