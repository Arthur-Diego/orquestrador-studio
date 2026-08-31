# ADR-026: Marca do rótulo por IMAGEM anexada (supersede da marca-texto) `[extensão]`

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-12
**ADRs relacionados:** ADR-002 (Higgsfield só via CLI oficial), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-020](./ADR-020-marca-validada-persistida-como-fonte-unica-das-sugestoes-de-termos.md)

## Contexto e Problema

Na etapa 3 (imagem base), o passo do **rótulo** (`kind="label"`, aula 009) trocava o rótulo da
embalagem pela marca do usuário. Até aqui a marca era **texto**: o painel 02 "Marca do rótulo"
tinha os campos `brandName` + `brandDesc` (nome + "como é a logo"), gravados em `base/brand.json`,
e a geração montava um prompt determinístico — `label_prompt(brand)` = *"Replace the product label
with the brand: {name}, {desc}. Keep the product colors..."* — enviado ao CLI com a imagem base
como referência.

O dono do produto avaliou que descrever a marca por texto **não serve**: ele já cria a própria
marca/logo como IMAGEM (por exemplo, no Higgsfield) e quer **anexá-la** para que ela seja aplicada
na imagem, em vez de tentar descrevê-la em palavras (o que produz rótulos genéricos, longe da
identidade real).

## Decisão

Substituir a marca-texto pela **marca-imagem anexada**, superseando o mecanismo `[extensão]` da
wave 1:

- O painel 02 deixa de ter os campos de texto e passa a ter um **upload de imagem** da marca
  (`brandImage` + área de drop + preview + "remover").
- A marca vira o arquivo `base/brand_image.png` (normalizado em PNG), no lugar de `brand.json`.
  Rotas: `GET/POST/DELETE /api/projects/{pid}/base/brand-image` (upload multipart).
- A geração do rótulo passa a mandar **duas** `image_references` — a imagem base (situação ou a
  limpeza `[extensão]` escolhida) **e** a marca-imagem — com um prompt fixo
  (`LABEL_IMAGE_PROMPT` = *"Apply the attached brand/logo image onto the product label. Keep the
  product colors, shape and everything else identical, realistic."*). Sem marca-imagem anexada,
  o rótulo é bloqueado com erro claro ("Anexe a imagem da marca antes de trocar o rótulo.").
- O `base.md`, o guia da etapa e o status (`label_ready`, antes `label_prompt_ready`) passam a
  refletir "marca anexada" em vez do texto da marca.

## Consequências

- **Fidelidade ao método (ADR-004):** continua `[extensão]` opt-in — a aula não manda usar marca
  por imagem; a marca `[extensão]` permanece na UI/código. Este ADR **supersede** apenas o formato
  do insumo (texto → imagem), não a etapa.
- **ADR-002 (Higgsfield só via CLI):** a aplicação da marca é por prompt + imagem de referência
  (sem máscara real), coerente com o inpaint-marcação; nada de automação da UI do provedor.
- **ADR-016 (livro-caixa):** o custo do rótulo segue registrado por `record_generation` em
  `start_generate` — nada muda no ledger (a mudança é só o insumo enviado ao CLI).
- **Limpeza:** saem `brand_get`/`brand_set`/`label_prompt`/`_brand_from_disk`/`BrandReq`/
  `brand.json` e os campos `brandName`/`brandDesc`. Não confundir com `refs/validated_brand.json`
  (ADR-020), que é a marca a REMOVER na limpeza (`kind="clean"`) — coisa distinta e preservada.
- **Testes:** contratos de serviço/rota/guia atualizados para a marca-imagem (upload multipart,
  duas referências na geração, `label_ready`). Suíte verde.
