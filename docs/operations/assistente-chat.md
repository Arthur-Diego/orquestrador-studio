# Manual — Assistente de chat do Studio `[extensão]`

O assistente conduz a criação de um vídeo do início ao fim conversando. Ele age pelas tools de um
servidor MCP do Studio e usa o **Claude Code CLI** com a sua assinatura (sem chave de API).
ADRs: 036 (runtime), 037 (MCP), 038 (humano-no-laço), 040 (agente isolado), 039 (personagem).

## Pré-requisitos
- **Claude Code CLI** instalado (`claude` no PATH). Sem ele, o painel avisa e não roda.
- Studio no ar: `make run` (http://127.0.0.1:8765).

## No app (painel lateral)
1. Abra o Studio no navegador; clique no botão **Assistente** (canto direito) ou nada — o dock
   abre pela última preferência.
2. Escreva o que quer ("cria uma campanha para a lata X e acha uma vibe"). O assistente lê o guia,
   propõe o próximo passo e executa.
3. **Você decide o visual e o gasto**: quando ele gera imagens, aparece uma **grade** para você
   escolher; quando a geração é paga (Higgsfield), aparece a **confirmação de custo** antes de
   gastar. Na exploração ele prefere o **motor local grátis**.
4. **Abas paralelas**: o `+` abre outra conversa (outra campanha). As abas mostram o status
   (gerando/erro) e o trabalho continua mesmo se você trocar de aba.
5. **Edição fina**: para pintar a máscara de inpaint ou mexer na timeline, ele abre a tela certa e
   espera você concluir.

## Personagem consistente
Na barra lateral, **Personagens**: crie um, **explore** variações (grátis), **fixe** a que você
acertou (gera o descritor de identidade), gere o **character sheet** e **aplique** à campanha. A
partir daí a mesma pessoa é reancorada nos prompts de imagem base e storyboard. Identidade paga
(Soul ID) é opcional e confirma antes.

## No terminal (mesmo MCP)
Com o Studio no ar e o `.mcp.json` do repositório, um `claude` comum enxerga as tools:

```bash
claude mcp list          # deve listar "studio"
claude "use as tools do studio: o que falta na campanha X?"
```

Skills prontas: `/studio-conduzir` (conduzir a campanha), `/studio-personagem` (personagem),
`/studio-ajuda` (dúvidas). As tools chegam como `mcp__studio__*`.

## Configuração (env)
- `STUDIO_CHAT_MODEL` — modelo do chat (vazio = default do seu CLI).
- `STUDIO_CHAT_MAX_ACTIVE` — máximo de conversas gerando ao mesmo tempo (default 3).
- `STUDIO_CHARACTERS` — pasta da biblioteca de personagens (default `<repo>/characters/`).

## Observabilidade
`GET /api/chats/{id}/trace` resume o que o assistente fez na aba (tools chamadas, custo estimado,
turnos). O transcript completo fica em `~/.orquestrador-studio/chats/<id>/events.jsonl`.

## Limites conhecidos
- Sem o CLI `claude`, o assistente não roda (é a ponte com o modelo).
- A nota de identidade facial depende do comando `engine faces` no motor local (a instalar).
- Soul ID exige plano pago na Higgsfield.
