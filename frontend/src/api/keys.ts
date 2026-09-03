/**
 * Chaves de cache do TanStack Query.
 *
 * **A separação entre `guia` e `guiaDaEtapa` é deliberada e estrutural.** O caminho óbvio seria
 * `["studio","guia",pid]` para o agregado e `["studio","guia",pid,step]` para a etapa — mas aí a
 * chave do agregado vira PREFIXO da chave de cada etapa, e `invalidateQueries` do agregado
 * invalidaria de quebra os 11 guias por etapa. O `scheduleGuideRefresh` do vanilla
 * (`studio/web/app.js:181-193`) recarrega **só** o agregado; um prefixo comum transformaria 1
 * request em 12. Segmentos diferentes tornam esse erro impossível de cometer, em vez de depender
 * de todo mundo lembrar de passar `exact: true`.
 */
export const chaves = {
  /** `GET /api/steps` — catálogo do curso, imutável durante a sessão. */
  etapas: () => ["studio", "etapas"] as const,
  /** `GET /api/projects` — lista de campanhas. */
  projetos: () => ["studio", "projetos"] as const,
  /** `GET /api/projects/{pid}` — `project.json` + progresso. */
  projeto: (pid: string) => ["studio", "projeto", pid] as const,
  /** `GET /api/projects/{pid}/guide` — o AGREGADO. Ver a nota sobre prefixo acima. */
  guia: (pid: string) => ["studio", "guia", pid] as const,
  /** `GET /api/projects/{pid}/guide/{step}` — guia de UMA etapa. */
  guiaDaEtapa: (pid: string, step: string) => ["studio", "guia-etapa", pid, step] as const,
  /** `GET /api/higgsfield/status` — status do CLI. */
  higgsfield: () => ["studio", "higgsfield"] as const,
} as const;
