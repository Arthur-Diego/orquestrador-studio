// Rótulos humanos das tools do MCP `studio` (ADR-037), para o chip e a linha de status do dock.
//
// Os textos são pt-BR no gerúndio e **sem** reticências: quem acrescenta o "…" é a linha de status,
// para o mesmo rótulo servir também ao chip. Toda tool registrada em `studio/mcp/server.py` tem de
// aparecer aqui — `tests/test_chat_tool_labels.py` é a guarda que cobra isso.

/** Mapa cru nome curto -> rótulo (exportado para o teste de cobertura). */
export const TOOL_LABELS: Record<string, string> = {
  projects: "Listando as campanhas",
  project: "Lendo a campanha",
  guide: "Conferindo o guia da campanha",
  guide_step: "Conferindo a etapa",
  steps: "Consultando o método do curso",
  doctor: "Checando as ferramentas",
  job: "Checando o trabalho em andamento",
  job_wait: "Aguardando geração",
  api_get: "Consultando dados do Studio",
  refs_suggest_terms: "Sugerindo termos de busca",
  refs_search: "Buscando referências no Pinterest",
  refs_pick: "Aguardando você escolher as referências",
  mood_prompt: "Escrevendo o prompt de vibe",
  mood_generate: "Gerando o mood board",
  mood_pick: "Aguardando você escolher o mood",
  base_prompt: "Escrevendo o prompt da imagem base",
  base_generate: "Gerando a imagem base",
  base_pick: "Aguardando você escolher a imagem base",
  // Wave 11 · F11 (revisão do upscale pelo chat): rótulo acrescentado no rebase, cobrado pela
  // guarda `tests/test_chat_tool_labels.py`.
  base_review: "Aguardando você revisar as novas imagens da base",
  storyboard_local_generate: "Gerando keyframes no motor local",
  storyboard_pick: "Aguardando você escolher os keyframes",
  // Wave 11 · F10 (créditos no chat): rótulo acrescentado no merge, cobrado pela guarda
  // `tests/test_chat_tool_labels.py`.
  credits_status: "Conferindo o saldo de créditos",
  storyboard_scenes: "Lendo as cenas do storyboard",
  // Wave 11 · F09 (geração por cena): rótulos acrescentados no rebase, cobrados pela guarda
  // `tests/test_chat_tool_labels.py`.
  storyboard_scene_generate: "Gerando os ângulos da cena",
  storyboard_scene_pick: "Aguardando você escolher e ordenar os frames da cena",
  // Wave 11 · F06 (roteiro, fotos nas cenas e prompts por foto): rótulos acrescentados no rebase,
  // cobrados pela guarda `tests/test_chat_tool_labels.py`.
  storyboard_script: "Escrevendo o roteiro das cenas",
  storyboard_script_wait: "Esperando o roteiro ficar pronto",
  storyboard_apply_script: "Aguardando você confirmar o roteiro nas cenas",
  storyboard_scene_attach: "Aguardando você escolher as fotos da cena",
  storyboard_keyframe_prompt: "Escrevendo o prompt da foto",
  storyboard_keyframe_set: "Gravando o texto que você escreveu",
  animate_shots: "Listando os shots para animar",
  animate_generate: "Animando o take",
  music_generate: "Gerando a trilha",
  edit_render: "Renderizando a montagem",
  export_render: "Exportando os formatos finais",
  export_qa: "Rodando o QA do export",
  portfolio: "Lendo o portfólio",
  ui_choose_one: "Aguardando sua escolha",
  ui_confirm: "Aguardando sua confirmação",
  ui_notify: "Avisando você",
  ui_show: "Mostrando as imagens",
  ui_open: "Aguardando você concluir na tela",
  // Wave 11 · F08 (card #88): as três tools que a frente da navegação acrescentou.
  // `ui_navigate` não bloqueia — o rótulo diz o que ela PEDE, não o que ela espera.
  ui_navigate: "Levando você para a tela",
  ui_choose_images: "Aguardando sua escolha das imagens",
  ui_form: "Aguardando você preencher",
  character_list: "Listando os personagens",
  character_create: "Criando o personagem",
  character_explore: "Explorando variações do personagem",
  character_pick: "Aguardando você escolher o personagem",
  character_sheet: "Gerando o character sheet",
  character_wait: "Aguardando a geração do personagem",
  character_apply: "Aplicando o personagem à campanha",
  character_bind_soul: "Treinando o Soul ID",
  character_score: "Medindo a semelhança do personagem",
  // Biblioteca de mood boards (wave 11 · F12, ADR-013): área global, sem campanha.
  moodboard_list: "Listando os mood boards",
  moodboard_get: "Lendo o mood board",
  moodboard_create: "Criando o mood board",
  moodboard_patch: "Salvando a vibe do mood board",
  moodboard_import: "Importando imagens para o mood board",
  moodboard_pick: "Aguardando você curar o mood board",
  moodboard_prompt: "Escrevendo o prompt de vibe do board",
  moodboard_delete: "Apagando o mood board",
  moodboard_multishot: "Gerando ângulos da imagem de vibe",
  moodboard_multishot_wait: "Aguardando os ângulos novos",
  vibes_list: "Listando o catálogo de vibes",
  vibes_pick: "Aguardando você escolher as fotos de vibe",
  escolhidas_list: "Listando as fotos escolhidas",
  mood_run: "Rodando a cadeia de mood",
  mood_run_wait: "Aguardando as pranchas de mood",
  mood_pull: "Puxando o mood board para a campanha",
};

/**
 * Rótulo humano de uma tool do MCP, para a linha de status e o chip.
 *
 * Aceita o nome cru (`mcp__studio__refs_search`) ou o curto (`refs_search`). Tool desconhecida cai
 * no fallback `studio.<nome>` — o mesmo texto que o dock produzia antes deste mapa para o nome cru,
 * que é o que o CLI emite —, de modo que uma tool nova nunca quebra a tela.
 */
export function toolLabel(name: string | undefined): string {
  if (!name) return "ferramenta";
  const curto = name.replace(/^mcp__studio__/, "");
  return TOOL_LABELS[curto] ?? `studio.${curto}`;
}
