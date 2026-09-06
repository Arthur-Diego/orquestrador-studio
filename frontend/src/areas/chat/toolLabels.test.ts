// Teste dos rótulos humanos das tools (T-TL-01..04): nome cru × curto, fallback, undefined e a
// integridade das 42 entradas do contrato 7 do FDD.
import { describe, expect, it } from "vitest";

import { TOOL_LABELS, toolLabel } from "./toolLabels";

// A tabela normativa do contrato 7 do FDD, transcrita. Qualquer edição de rótulo em `toolLabels.ts`
// que não passe pelo FDD reprova aqui — é o par frontend da guarda `tests/test_chat_tool_labels.py`.
const ESPERADO: Record<string, string> = {
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
  storyboard_local_generate: "Gerando keyframes no motor local",
  storyboard_pick: "Aguardando você escolher os keyframes",
  storyboard_scenes: "Lendo as cenas do storyboard",
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
  character_list: "Listando os personagens",
  character_create: "Criando o personagem",
  character_explore: "Explorando variações do personagem",
  character_pick: "Aguardando você escolher o personagem",
  character_sheet: "Gerando o character sheet",
  character_wait: "Aguardando a geração do personagem",
  character_apply: "Aplicando o personagem à campanha",
  character_bind_soul: "Treinando o Soul ID",
  character_score: "Medindo a semelhança do personagem",
};

describe("toolLabel", () => {
  // T-TL-01
  it("aceita o nome cru e o curto com o mesmo rótulo", () => {
    expect(toolLabel("mcp__studio__refs_search")).toBe("Buscando referências no Pinterest");
    expect(toolLabel("refs_search")).toBe(toolLabel("mcp__studio__refs_search"));
    expect(toolLabel("mcp__studio__job_wait")).toBe(toolLabel("job_wait"));
  });

  // T-TL-02
  it("cai no fallback studio.<nome> para tool desconhecida", () => {
    expect(toolLabel("mcp__studio__tool_que_nao_existe")).toBe("studio.tool_que_nao_existe");
    expect(toolLabel("tool_que_nao_existe")).toBe("studio.tool_que_nao_existe");
  });

  // T-TL-03
  it("não quebra com undefined", () => {
    expect(toolLabel(undefined)).toBe("ferramenta");
    expect(toolLabel("")).toBe("ferramenta");
  });

  // T-TL-04
  it("tem as 42 entradas do contrato, com os textos exatos", () => {
    expect(TOOL_LABELS).toEqual(ESPERADO);
    expect(Object.keys(TOOL_LABELS)).toHaveLength(42);
  });

  it("nenhum rótulo tem reticências (quem acrescenta é a linha de status)", () => {
    for (const [nome, rotulo] of Object.entries(TOOL_LABELS)) {
      expect(rotulo, nome).not.toMatch(/[…]|\.\.\.$/);
      expect(rotulo.trim(), nome).toBe(rotulo);
      expect(rotulo.length, nome).toBeGreaterThan(0);
    }
  });

  it("as chaves são nomes curtos, sem o prefixo do MCP", () => {
    for (const nome of Object.keys(TOOL_LABELS)) {
      expect(nome).not.toMatch(/^mcp__/);
    }
  });
});
