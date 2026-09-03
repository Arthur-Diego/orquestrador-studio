# Contrato de saída

## Saída humana em Markdown

Use a seguinte ordem:

1. `Resumo executivo`
2. `DNA visual observado`
3. `Interpretação e confiança`
4. `Paleta aproximada`
5. `Consultas por função`
6. `Plano de curadoria`
7. `Referências verificadas` quando houver busca
8. `Incertezas e próximos ajustes`

## Saída JSON

Use [../assets/visual-dna-template.json](../assets/visual-dna-template.json) como estrutura. Regras:

- JSON válido, UTF-8, sem comentários.
- Preserve arrays vazios em vez de inventar dados.
- Use `null` para o que não pode ser determinado.
- HEX deve usar `#RRGGBB` em maiúsculas.
- `confidence` aceita somente `low`, `medium` ou `high`.
- `observation_type` aceita `observed`, `inferred` ou `unknown`.
- Pontuações de referência são inteiros de 0 a 5.
- URLs devem apontar para páginas de origem, não para miniaturas temporárias.

## Campos essenciais

| Campo | Finalidade |
| --- | --- |
| `source` | identifica a imagem analisada sem presumir autoria |
| `summary` | sintetiza a direção visual |
| `visual_dna` | registra evidências por dimensão |
| `aesthetics` | guarda vibe principal, relacionadas e confiança |
| `palette` | oferece cores aproximadas e seus papéis |
| `search_queries` | organiza pesquisas por função e plataforma |
| `moodboard_plan` | define composição e quantidade |
| `references` | registra resultados verificáveis, se encontrados |
| `uncertainties` | torna explícitas limitações e hipóteses |

## Validação

Quando gerar um arquivo JSON, execute:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_visual_dna.py" caminho/visual-dna.json
```

O validador confirma estrutura mínima, valores enumerados, HEX, URLs, tipos e faixas. Ele não confirma se a interpretação estética está correta nem se uma licença é válida.
