---
name: visual-dna-moodboard
description: Analisa uma imagem de referência, extrai seu DNA visual, cria termos de busca e organiza referências complementares para um moodboard coerente. Use quando o usuário enviar ou indicar uma imagem e pedir leitura estética, paleta, vibe, direção de arte, pesquisas visuais ou planejamento de moodboard. Não use para identificar pessoas, autenticar obras ou declarar licenças de imagens sem fonte verificável.
license: MIT
compatibility: Claude Code 2.x ou ambiente compatível com Agent Skills que aceite imagens; busca na web é opcional.
metadata:
  version: 1.0.0
  category: visual-direction
  language: multilingual
allowed-tools:
  - Read
  - Glob
  - Grep
  - WebSearch
  - WebFetch
---

# Visual DNA Moodboard

Transforme uma imagem-base em uma direção visual explícita, pesquisável e útil para curadoria. Responda no idioma do usuário; escreva termos de busca principalmente em inglês e acrescente equivalentes locais apenas quando melhorarem os resultados.

## Entrada mínima

Exija pelo menos uma imagem visível ou um caminho/URL acessível. Aceite, quando fornecidos: objetivo do moodboard, público, formato final, plataforma de busca, quantidade de referências e restrições de marca ou direitos.

Se não houver imagem acessível, peça que o usuário a anexe ou forneça um caminho/URL válido. Não invente uma análise visual a partir de uma descrição incompleta.

## Fluxo principal

1. Inspecione a imagem inteira antes de nomear a estética.
2. Separe observação de interpretação:
   - `Observado`: evidência diretamente visível.
   - `Inferido`: leitura estética plausível, marcada como tal.
   - `Desconhecido`: dado que a imagem não permite concluir.
3. Extraia o DNA visual usando [references/visual-analysis-rubric.md](references/visual-analysis-rubric.md).
4. Dê uma vibe principal e até quatro relacionadas. Use rótulos reconhecíveis em pesquisa; não force um estilo famoso quando os sinais forem fracos.
5. Gere uma paleta de 4 a 8 cores em HEX. Trate cores amostradas visualmente como aproximações, salvo se uma ferramenta de medição tiver sido usada.
6. Converta os atributos em consultas variadas usando [references/search-strategy.md](references/search-strategy.md).
7. Distribua as consultas por funções de moodboard, não apenas por imagens semelhantes.
8. Se houver busca visual/web disponível e o usuário pediu referências, pesquise, filtre e cite as páginas de origem. Caso contrário, entregue consultas prontas e indique onde usá-las.
9. Monte a recomendação de curadoria com [references/moodboard-curation.md](references/moodboard-curation.md).
10. Entregue o resultado conforme [references/output-contract.md](references/output-contract.md).

## Regras de análise

- Descreva pessoas somente por características visuais relevantes à direção de arte. Não tente identificar indivíduos nem inferir atributos sensíveis.
- Não confunda tema com técnica: `cyberpunk` pode ser tema; `fotografia cinematográfica`, `cel shading` e `render 3D` são técnicas/aparências.
- Diferencie `semelhante` de `complementar`. Um moodboard útil amplia o universo visual sem repetir o mesmo enquadramento.
- Preserve os sinais dominantes da imagem: temperatura, contraste, saturação, materiais, época percebida e emoção.
- Evite certeza falsa sobre câmera, lente, software, artista ou período. Use “provável”, “aparenta” ou “inspirado em” quando não houver evidência verificável.
- Não atribua autoria, marca, licença ou permissão de uso pela aparência. Para uso comercial, recomende verificar a licença na fonte original.
- Não use nomes de artistas vivos como atalho estilístico. Descreva características visuais observáveis e movimentos amplos.

## Estratégia de referências

Busque diversidade funcional no mesmo universo visual:

- imagem hero / narrativa
- ambiente / arquitetura
- personagem / styling
- objetos / props
- luz / cor
- materiais / textura
- tipografia / design gráfico
- interface / elementos digitais
- interpretação 2D
- interpretação 3D

Para cada categoria, produza ao menos uma consulta específica. Quando o usuário pedir poucas referências, priorize hero, atmosfera, textura, objeto, tipografia e uma tradução 2D ou 3D.

## Busca e seleção

Quando pesquisar referências:

- Prefira a fonte original ou portfólios confiáveis a agregadores que removem autoria.
- Registre título ou descrição curta, criador quando verificável, URL da página e papel no moodboard.
- Não apresente miniaturas ou URLs temporárias como fonte permanente.
- Não diga que uma referência é “livre para uso” sem verificar os termos da página original.
- Pinterest pode ser usado para descoberta; para licenciamento ou crédito, siga o pin até a origem.
- Elimine duplicatas, imagens quase idênticas e itens que introduzam uma paleta ou época conflitante sem justificativa.

## Qualidade da curadoria

Avalie cada candidata em quatro eixos de 0 a 5:

- coerência de cor e luz
- coerência de forma, material e época
- valor complementar para a narrativa
- adequação ao objetivo do usuário

Use a soma apenas como apoio. Não invente precisão matemática nem chame o resultado de “similaridade visual” se não houve comparação computacional. Explique em uma frase por que cada selecionada pertence ao conjunto.

## Saída padrão

Entregue, nesta ordem:

1. resumo executivo em 2 a 4 frases
2. DNA visual
3. vibe principal e vibes relacionadas
4. paleta HEX aproximada
5. consultas prontas por categoria
6. plano de moodboard
7. referências encontradas, se houve busca
8. riscos, incertezas e próximos ajustes

Use tabelas apenas para paleta, consultas, referências ou pontuações. Para uma análise curta, compacte as seções sem omitir a distinção entre observado e inferido.

## Recursos

- Leia [references/visual-analysis-rubric.md](references/visual-analysis-rubric.md) ao analisar a imagem.
- Leia [references/search-strategy.md](references/search-strategy.md) ao gerar pesquisas ou buscar referências.
- Leia [references/moodboard-curation.md](references/moodboard-curation.md) ao selecionar ou diagramar o moodboard.
- Leia [references/output-contract.md](references/output-contract.md) quando o usuário pedir JSON, automação, integração ou saída estruturada.
- Consulte [examples/matrix-core-example.md](examples/matrix-core-example.md) somente quando precisar de um exemplo completo de saída tecnológica realista + 2D + 3D. O equivalente estruturado está em [examples/matrix-core-output.json](examples/matrix-core-output.json).
- Use [assets/visual-dna-template.json](assets/visual-dna-template.json) como base para saída JSON.
- Valide JSON estruturado com `python3 "${CLAUDE_SKILL_DIR}/scripts/validate_visual_dna.py" <arquivo.json>` quando Bash estiver disponível e o usuário precisar de um artefato validado.

## Limites operacionais

Não baixe, publique, envie ou reutilize imagens externamente sem pedido explícito. Não faça login em plataformas nem contorne bloqueios. Se a busca falhar, entregue um plano de busca de alta qualidade em vez de fabricar fontes ou resultados.
