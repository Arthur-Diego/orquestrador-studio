/**
 * O equivalente TanStack Query de `Studio.onGuide` + `recomputeOverview` + `scheduleGuideRefresh`.
 *
 * ## O que o vanilla faz hoje (`studio/web/app.js`)
 *
 * ```js
 * onGuide(stepId, g) {
 *   if (g) { guideById[stepId] = g; recomputeOverview(); renderMenu(); renderTopbar(); }
 *   scheduleGuideRefresh();                                    // debounce de 400 ms
 * }
 * ```
 *
 * `recomputeOverview()` (l.171-179) **muta `guideAll` in-place** a partir de `guideById`: um cache
 * derivado escrito por fora do fetch que o alimenta. `scheduleGuideRefresh()` (l.181-193) agenda,
 * com 400 ms de debounce e um único timer global, um GET do agregado que sobrescreve tudo.
 *
 * A dupla existe porque `Studio.ui.renderGuide(stepId)` — chamado por `ctx.guide()` depois de
 * QUALQUER ação que mexa em artefato — já traz o guia daquela etapa de graça. Atualizar o rail na
 * hora com esse dado evita o pisca de esperar o servidor; o refetch atrasado corrige os campos
 * agregados que só o backend sabe. Uma tela pode chamar `ctx.guide()` várias vezes numa mesma
 * ação (upload de 5 arquivos, por exemplo): sem o debounce seriam 5 GETs do agregado, cada um
 * disparando um re-render do rail inteiro.
 *
 * ## Como isso vira TanStack Query
 *
 * | vanilla | aqui |
 * | --- | --- |
 * | `guideById[stepId] = g` | `setQueryData(chaves.guiaDaEtapa(pid, stepId), g)` |
 * | `recomputeOverview()` | `setQueryData(chaves.guia(pid), old => recomputarAgregado(...))` |
 * | `renderMenu(); renderTopbar()` | re-render dos assinantes da query (automático) |
 * | `scheduleGuideRefresh()` | `invalidateQueries(chaves.guia(pid))` atrasado em 400 ms |
 *
 * O que se preserva é o **comportamento observável**: uma atualização otimista imediata a partir de
 * dado que o backend já mandou, seguida de no máximo um request por rajada de 400 ms.
 *
 * ## ADR-010 (a) — o invariante
 *
 * Nada aqui calcula prontidão de etapa. `recomputarAgregado` **copia** o `status` que veio do
 * backend em cada `Guide` e só re-deriva os contadores do agregado (`done`, `total`, `progress`,
 * `current`) a partir desses status — exatamente as quatro linhas que `recomputeOverview()` já
 * fazia. Se alguém precisar de um status de etapa e ele não estiver no guia, a resposta é pedir o
 * guia ao backend, nunca inferir daqui.
 */
import type { QueryClient } from "@tanstack/react-query";

import { chaves } from "./keys";
import type { Guide, GuideAll } from "./types";

/** Debounce de `scheduleGuideRefresh` (`studio/web/app.js:193`). Mudar isto muda comportamento. */
export const DEBOUNCE_GUIA_MS = 400;

/**
 * Reescreve o agregado depois que uma etapa devolveu um guia novo — o `recomputeOverview()` do
 * vanilla, sem mutação in-place (o TanStack Query compara por referência para decidir re-render).
 *
 * `ordem` são os ids de `GET /api/steps` na ordem do curso: é ela que decide a posição das etapas
 * no rail, e é o que permite que um guia de etapa que ainda não estava no agregado seja
 * **inserido** no lugar certo, e não só substituído.
 *
 * Detalhes copiados de propósito:
 *
 * - `progress` é `done / total` **sem arredondar**, enquanto o backend devolve `round(x, 2)`
 *   (`studio/app.py::_overview`). Ou seja: o agregado local já diverge do agregado do servidor na
 *   2ª casa decimal HOJE, até o refresh de 400 ms chegar e reconciliar. É comportamento existente,
 *   não bug novo — arredondar aqui seria mudar a UI.
 * - etapas do catálogo sem guia somem (`filter(Boolean)` no vanilla), e é assim que as etapas
 *   `soon` ficam de fora do agregado.
 *
 * Divergência única, registrada: quando `ordem` chega vazia — `/api/steps` ainda não respondeu —,
 * a ordem já existente em `atual.steps` é usada como fallback, em vez de zerar o agregado. No
 * vanilla esse estado é inalcançável (o `boot()` espera `/api/steps` antes de qualquer tela
 * montar), mas com queries paralelas ele passa a ser alcançável, e a tradução literal apagaria o
 * rail por uma fração de segundo.
 */
export function recomputarAgregado(
  atual: GuideAll,
  ordem: readonly string[],
  stepId: string,
  g: Guide,
): GuideAll {
  const porId = new Map<string, Guide>(atual.steps.map((s) => [s.id, s]));
  porId.set(stepId, g);

  const ids = ordem.length > 0 ? ordem : [...atual.steps.map((s) => s.id), stepId];
  const vistos = new Set<string>();
  const steps: Guide[] = [];
  for (const id of ids) {
    const guia = porId.get(id);
    if (guia && !vistos.has(id)) {
      vistos.add(id);
      steps.push(guia);
    }
  }

  const done = steps.filter((s) => s.status === "done").length;
  const total = steps.length;
  const proxima = steps.find((s) => s.status !== "done");
  return { steps, done, total, progress: total ? done / total : 0, current: proxima ? proxima.id : null };
}

/**
 * O timer único e global de `scheduleGuideRefresh` (`refreshTimer`, `app.js:40`).
 *
 * É um objeto e não uma variável de módulo solta para que cada teste (e, se um dia for preciso,
 * cada shell) tenha o seu — mas a instância `agendadorDoGuia` abaixo é **uma só para o app**,
 * porque é isso que o vanilla tem: um `clearTimeout` global, então a 5ª chamada de `ctx.guide()`
 * numa rajada cancela as 4 anteriores independentemente de qual tela as disparou.
 */
export class AgendadorDeRefresh {
  private timer: ReturnType<typeof setTimeout> | null = null;
  /** `erasableSyntaxOnly` do tsconfig proíbe propriedade de parâmetro — o campo é declarado aqui. */
  private readonly atrasoMs: number;

  constructor(atrasoMs: number = DEBOUNCE_GUIA_MS) {
    this.atrasoMs = atrasoMs;
  }

  /**
   * Agenda o refetch do agregado, cancelando o anterior.
   *
   * `pid` é um **getter**, não um valor: o vanilla lê a variável de módulo `pid` DENTRO do
   * `setTimeout` (`if (!pid) return;`, l.184), então trocar de campanha durante os 400 ms aborta o
   * refresh da campanha antiga. Capturar o pid no agendamento faria um request que o vanilla não faz.
   */
  agendar(qc: QueryClient, pid: () => string | null): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      const atual = pid();
      if (!atual) return;
      // `exact` porque o agregado é o único alvo: as queries de guia por etapa têm chave de
      // segmento próprio (ver `keys.ts`) e não devem ser refeitas junto.
      //
      // Sem `.catch`: `invalidateQueries` não rejeita por falha de rede — o erro fica na query, e
      // os assinantes continuam lendo o `data` anterior. É o equivalente do `catch {}` do vanilla
      // ("o guia é informativo: falhar aqui não pode atrapalhar a tela"), que também deixava o
      // `guideAll` velho no lugar.
      void qc.invalidateQueries({ queryKey: chaves.guia(atual), exact: true });
    }, this.atrasoMs);
  }

  /**
   * Cancela um refresh pendente.
   *
   * O vanilla nunca cancela — nada desmonta lá. Aqui isto existe para os testes e para a E3 poder
   * limpar o timer ao derrubar o shell; o hook `useGuideSync` **não** cancela no unmount de
   * propósito, porque abortar um refresh já agendado seria mudança de comportamento.
   */
  cancelar(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  /** Só para teste: existe refresh pendente? */
  get pendente(): boolean {
    return this.timer !== null;
  }
}

/** A instância do app — o `refreshTimer` global do `app.js`. */
export const agendadorDoGuia = new AgendadorDeRefresh();

/**
 * `Studio.onGuide(stepId, g)` (`studio/web/app.js:64-67`), inteiro.
 *
 * Ordem e condições são as do vanilla: a atualização otimista só acontece com `g` truthy, o
 * agregado só é recomputado se já existir no cache (`if (!guideAll) return;`), e o refresh é
 * agendado SEMPRE — inclusive quando `g` é nulo, que é o caso de o `renderGuide` ter falhado.
 */
export function aplicarGuiaDaEtapa(
  qc: QueryClient,
  pid: () => string | null,
  stepId: string,
  g: Guide | null | undefined,
  ordem: readonly string[],
  agendador: AgendadorDeRefresh = agendadorDoGuia,
): void {
  const atual = pid();
  if (g && atual) {
    qc.setQueryData(chaves.guiaDaEtapa(atual, stepId), g);
    qc.setQueryData<GuideAll>(chaves.guia(atual), (anterior) =>
      anterior ? recomputarAgregado(anterior, ordem, stepId, g) : anterior,
    );
  }
  agendador.agendar(qc, pid);
}
