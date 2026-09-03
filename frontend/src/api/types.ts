/**
 * Formas de RESPOSTA do núcleo — a metade que o `schema.ts` gerado não consegue cobrir.
 *
 * ## Por que estes tipos são escritos à mão
 *
 * Nenhuma rota do backend declara `response_model`. O `/openapi.json` publicado traz, em todos os
 * 200 das 201 rotas, `"content": {"application/json": {"schema": {}}}` — e `openapi-typescript`
 * traduz isso fielmente para `unknown`. O contrato gerado é, portanto, exato no que o FastAPI
 * realmente descreve (caminhos, parâmetros de rota, query e **corpos de requisição**, que vêm dos
 * modelos Pydantic) e vazio no que ele não descreve (respostas).
 *
 * Fazer o backend declarar `response_model` resolveria isso na raiz e é a correção certa — mas é
 * mudança de `router.py`, que esta frente está proibida de tocar (invariante 2 do card [REACT-02]).
 * Fica registrado como pendência para a integração, não como dívida escondida.
 *
 * Estes tipos são, então, **declarações do observado**, com a origem anotada em cada um. Eles não
 * inventam campo nenhum: cada campo abaixo é escrito por uma linha identificada do backend.
 *
 * ## ADR-010 (a) — a regra que governa este arquivo
 *
 * `Guide.status` é o estado de prontidão de uma etapa e vem SEMPRE de
 * `GET /api/projects/{pid}/guide` (ou `/guide/{step}`). O frontend nunca o calcula, nunca o
 * deriva de artefatos e nunca o corrige. Não existe, e não pode passar a existir, função neste
 * pacote que produza um `StepStatus` — só funções que copiam o que o backend mandou.
 */

/** Estados de uma etapa. Fonte: `studio/common/guide.py::STATUS`. */
export type StepStatus = "todo" | "blocked" | "in_progress" | "done" | "unknown";

/** Estados de um item de guia (input/output/validation). Fonte: `guide.py::CHECK_STATUS` + `_item`. */
export type ItemStatus = "ok" | "warn" | "fail" | "todo";

/** Cor do chip de resumo do guia. Fonte: `guide.py::Guide.build(summary_kind=...)`. */
export type SummaryKind = "ok" | "warn" | "fail" | "info" | "mode";

/** Um input, output ou validação do guia. Fonte: `guide.py::_item` (os 3 últimos são opcionais). */
export interface GuideItem {
  id: string;
  label: string;
  status: ItemStatus;
  detail?: string;
  fix?: string;
  /** Id da etapa que produz o artefato — vira link "ir para lá" na UI. Só em `inputs`. */
  step?: string;
}

/**
 * Guia de UMA etapa. Fonte: `guide.py::Guide.build()` e `guide.py::generic_guide()`.
 *
 * Todos os campos são sempre devolvidos (o backend garante isso de propósito, para o frontend
 * nunca precisar checar se a chave existe) — menos `detail`, que só aparece no guia genérico
 * quando o hook da etapa levantou exceção.
 */
export interface Guide {
  id: string;
  /** Número da etapa no catálogo do curso (1..10). `null` em `META` sem `n`. */
  n: number | null;
  title: string;
  aula: string;
  status: StepStatus;
  /** Fração de `outputs` com status `ok`, arredondada em 2 casas pelo backend. */
  progress: number;
  /** O que a aula manda fazer nesta etapa (ADR-004 — texto de curso, não muda). */
  what: string;
  checklist: string[];
  inputs: GuideItem[];
  outputs: GuideItem[];
  validations: GuideItem[];
  /** Labels de tudo que falta (inputs + outputs não `ok`). */
  missing: string[];
  summary: string | null;
  summary_kind: SummaryKind | null;
  next_action: string;
  next_step: string | null;
  /** Só no guia genérico de hook que explodiu: `"<TipoDoErro>: <mensagem>"`. */
  detail?: string;
}

/**
 * Agregado de `GET /api/projects/{pid}/guide`. Fonte: `studio/app.py::project_guide`, que devolve
 * `{"steps": guides, **_overview(guides)}` — e `_overview` produz `done`, `total`, `progress` e
 * `current`.
 */
export interface GuideAll {
  steps: Guide[];
  done: number;
  total: number;
  /** `round(done / total, 2)` no backend. Ver a nota de arredondamento em `guide-sync.ts`. */
  progress: number;
  /** Id da primeira etapa com status != `done`; `null` quando a campanha inteira está pronta. */
  current: string | null;
}

/**
 * Item de `GET /api/steps`. Fonte: `studio/steps.py::all_steps()` — o catálogo `SOON` fundido com
 * o `META` do plugin quando a etapa está implementada.
 */
export interface Step {
  id: string;
  /** Posição no pipeline do curso (1..10). É a chave de ordenação do catálogo. */
  n: number;
  title: string;
  /** Aula do curso que ensina a etapa. Pode ser composta: `"010+011"`. */
  aula: string;
  desc: string;
  /** `ready` = a etapa tem plugin; `soon` = está só no catálogo. */
  status: "ready" | "soon";
}

/**
 * `project.json` como `GET /api/projects` o devolve. Fonte: `studio/refs/service.py::create_project`
 * (campos base) + `studio/app.py::PATCHABLE` (campos que o PATCH acrescenta com o tempo).
 *
 * `aspect_ratio` e `brand` são `[extensão]` e só existem depois de um PATCH — projeto recém-criado
 * não tem a chave.
 */
export interface Project {
  id: string;
  name: string;
  product: string;
  vibe: string;
  /** `YYYY-MM-DD` da criação. */
  created: string;
  /** `[extensão]` — `16:9` | `9:16` | `1:1`. Ausente até o primeiro PATCH. */
  aspect_ratio?: string;
  /** `[extensão]` (ADR-026) — marca do rótulo da etapa 3. Ausente até o primeiro PATCH. */
  brand?: string;
}

/**
 * `GET /api/projects/{pid}`: o `project.json` MAIS o agregado do guia.
 * Fonte: `studio/app.py::project` — `{**meta, "progress": ..., "current": ...}`.
 */
export interface ProjectDetail extends Project {
  progress: number;
  current: string | null;
}

/**
 * `GET /api/higgsfield/status`. Fonte: `studio/higgsfield.py::status` e `_status_uncached`.
 *
 * Três formas possíveis, e é por isso que quase tudo é opcional: sem binário
 * (`{installed:false, logged_in:false}`), com binário e sem login (`+ error`), logado
 * (`+ email, plan, credits, raw`).
 */
export interface HiggsfieldStatus {
  installed: boolean;
  logged_in: boolean;
  email?: string | null;
  plan?: string | null;
  credits?: number | string | null;
  error?: string;
  raw?: unknown;
}
