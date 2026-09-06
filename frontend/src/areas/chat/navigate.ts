// Decisão de navegação do chat — Wave 11 · frente F08 (card #88, ADH-OS-20260906-10). `[extensão]`
//
// "O assistente pediu para ir para `X`: eu vou, ou recuso e digo por quê?" — essa pergunta, e só
// ela, mora aqui. É uma função PURA: sem React, sem rede, sem `location`, sem `localStorage`. O
// `ChatDock` traz os fatos (alvo, campanha, catálogo, guia) e recebe de volta uma decisão pronta,
// com o texto da recusa já formado.
//
// ## Por que isto não mora no ChatDock
//
// `ChatDock.tsx` é o arquivo mais disputado da wave (risco R3 do FDD): quatro frentes o editam ao
// mesmo tempo. Toda lógica que sai dele é conflito de rebase que não acontece — e, de quebra, vira
// teste de unidade sem jsdom.
//
// ## As duas perguntas que NÃO são a mesma (risco R5)
//
// - **Navegável**: a etapa existe no catálogo `/api/steps` com `status === "ready"`, isto é, o
//   plugin de tela está instalado nesta versão do Studio (`Step.status` só tem `ready`/`soon`).
// - **Liberada**: o guia daquela etapa não está `blocked`, isto é, os insumos das etapas anteriores
//   existem (`Guide.status` é `StepStatus`, cinco valores).
//
// São duas fontes distintas, com dois textos de recusa distintos: "essa tela ainda não existe" e
// "essa tela existe, mas falta X". Confundi-las é dizer ao usuário que a etapa não existe quando na
// verdade falta uma referência.
//
// ## O que este módulo NÃO faz (ADR-010 item a)
//
// Não deriva prontidão. Não olha `outputs`, não conta arquivo, não infere status: só compara os
// campos que o backend mandou. Quando o guia não veio (query em erro, ou ainda carregando quando o
// teto de 1500 ms estourou), a decisão é NAVEGAR — o guia é informativo, e a guarda do roteador
// continua sendo a última linha de defesa (E8 do FDD).
import type { GuideAll, Step } from "../../api";
import { CHAR_ROUTE, CR_ROUTE, MB_ROUTE } from "../../shell/constants";

/** Por que a navegação foi recusada. Diagnóstico e teste — o usuário lê `texto`. */
export type MotivoDaRecusa =
  /** `target` vazio, só espaços, não string, ou com barras a mais (E4/E5). */
  | "pedido_invalido"
  /** Alvo de campanha sem campanha aberta (E10, A4). */
  | "sem_campanha"
  /** Etapa `soon`, id desconhecido, ou alvo com `/` fora das áreas globais (E5/E6, A3). */
  | "tela_inexistente"
  /** Etapa navegável, mas com o guia `blocked` (E7, A2). */
  | "etapa_bloqueada";

/**
 * O veredito. Discriminado por `acao` para o dock não ter que adivinhar o que fazer.
 *
 * No ramo `navegar`, `target` é o alvo JÁ NORMALIZADO — é ele que vai para `navigate()`, não o
 * `target` cru do evento (`creditos/qualquer-coisa` normaliza para `creditos`, porque a área não
 * tem sub-tela; ver a tabela do Contrato 5 do FDD).
 */
export type DecisaoDeNavegacao =
  | { readonly acao: "navegar"; readonly target: string }
  | { readonly acao: "recusar"; readonly motivo: MotivoDaRecusa; readonly texto: string };

/** Prefixos de rota reservados (ADR-013/016/039). Vêm do shell — nunca literais duplicados aqui. */
const AREAS_GLOBAIS: readonly string[] = [MB_ROUTE, CHAR_ROUTE, CR_ROUTE];

/** Áreas globais que têm sub-tela. `creditos` não tem: a sub-rota é descartada (Contrato 5). */
const AREAS_COM_SUB: readonly string[] = [MB_ROUTE, CHAR_ROUTE];

/** Quantos itens de `missing` cabem na recusa antes de virar parede de texto (A2). */
const MAX_ITENS_FALTANDO = 3;

/** A view que toda campanha tem, sempre, sem passar pelo catálogo de etapas. */
const OVERVIEW = "overview";

function textoPedidoInvalido(): string {
  return "Ignorei um pedido de navegação inválido: o assistente não disse para onde ir.";
}

function textoSemCampanha(): string {
  return "Abra uma campanha antes de pedir para eu trocar de tela.";
}

function textoTelaInexistente(alvo: string): string {
  return `A tela da etapa "${alvo}" ainda não existe nesta versão do Studio.`;
}

/**
 * `Não abri a etapa Mood board: falta imagem base final; ao menos 1 referência escolhida.`
 *
 * Os itens saem de `Guide.missing` (labels já prontos do backend), no máximo três. Guia bloqueado
 * com `missing` vazio não deveria acontecer, mas se acontecer o usuário ainda merece uma frase.
 */
function textoEtapaBloqueada(titulo: string, faltando: readonly string[]): string {
  const itens = faltando.slice(0, MAX_ITENS_FALTANDO);
  if (!itens.length) return `Não abri a etapa ${titulo}: ela ainda está bloqueada.`;
  return `Não abri a etapa ${titulo}: ${itens.join("; ")}.`;
}

/**
 * Decide se o alvo pedido pelo assistente pode virar uma troca de tela.
 *
 * @param alvo `target` do evento. Vem do agente, então chega como `unknown` de propósito: o
 *   vocabulário não é validado por nenhum schema no caminho (E4 — a defesa é do cliente).
 * @param pid campanha aberta, ou `null`.
 * @param etapas catálogo `/api/steps`.
 * @param guiaAgregado agregado do guia da campanha, ou `null` quando indisponível (E8).
 */
export function decidirNavegacao(
  alvo: unknown,
  pid: string | null,
  etapas: readonly Step[],
  guiaAgregado: GuideAll | null,
): DecisaoDeNavegacao {
  if (typeof alvo !== "string") {
    return { acao: "recusar", motivo: "pedido_invalido", texto: textoPedidoInvalido() };
  }
  const target = alvo.trim();
  if (!target) {
    return { acao: "recusar", motivo: "pedido_invalido", texto: textoPedidoInvalido() };
  }

  // Áreas globais primeiro: não têm guia (ADR-013/016/039) e funcionam sem campanha nenhuma.
  const segmentos = target.split("/");
  const prefixo = segmentos[0]!;
  if (AREAS_GLOBAIS.includes(prefixo)) {
    // Mais de um sub-segmento não cabe na gramática do hash (`#/<a>/<b>`), então não é alvo válido.
    if (segmentos.length > 2) {
      return { acao: "recusar", motivo: "pedido_invalido", texto: textoPedidoInvalido() };
    }
    const sub = segmentos[1]?.trim();
    const comSub = sub && AREAS_COM_SUB.includes(prefixo);
    return { acao: "navegar", target: comSub ? `${prefixo}/${sub}` : prefixo };
  }

  // Fora das áreas globais, uma barra só produziria `#/<pid>/p1%2Fmood` (E5): recusa com o mesmo
  // texto de A3, porque para o usuário o efeito é o mesmo — aquela tela não existe.
  if (segmentos.length > 1) {
    return { acao: "recusar", motivo: "tela_inexistente", texto: textoTelaInexistente(target) };
  }

  // Daqui para baixo o alvo é de campanha, e campanha é obrigatória (A4).
  if (!pid) {
    return { acao: "recusar", motivo: "sem_campanha", texto: textoSemCampanha() };
  }
  if (target === OVERVIEW) return { acao: "navegar", target };

  // Navegável? (catálogo, não guia)
  const etapa = etapas.find((s) => s.id === target);
  if (!etapa || etapa.status !== "ready") {
    return { acao: "recusar", motivo: "tela_inexistente", texto: textoTelaInexistente(target) };
  }

  // Liberada? (guia, não catálogo). Guia ausente não bloqueia nada — é informativo (E8).
  const guia = guiaAgregado?.steps.find((g) => g.id === target);
  if (guia?.status === "blocked") {
    return {
      acao: "recusar",
      motivo: "etapa_bloqueada",
      texto: textoEtapaBloqueada(etapa.title || guia.title || target, guia.missing ?? []),
    };
  }
  return { acao: "navegar", target };
}
