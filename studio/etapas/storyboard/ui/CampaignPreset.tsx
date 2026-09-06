// `[extensão]` **Padrão visual da campanha** (Wave 11 · F06, card #98 — FDD §4 fluxo 3).
//
// Mora fora de `Ideation.tsx` porque não é da etapa 4: o mesmo bloco é montado no topo da etapa 3
// (a ação `base` é uma das cinco que ele nivela). Aqui ficam também os TRÊS ESTADOS do preset
// (invariante 6 do FDD), que a etapa 4 usa no seletor por foto — um único lugar define o que
// `""`, `"off"` e um id significam, para que a tela e o corpo HTTP nunca divirjam.
import { useState } from "react";

import type { PresetDefaults, RealismPreset } from "./types";

// Os três estados do preset vivem no VALOR do `<select>`, para que não exista uma segunda
// tradução entre a tela e o corpo HTTP: `""` herda (a chave sai AUSENTE do corpo), `"off"` é
// "sem preset" (`null` no corpo) e qualquer outro valor é o id do catálogo. Invariante 6.
export const PRESET_INHERIT = "";
export const PRESET_OFF = "off";
/** Valor sentinela do seletor da campanha quando as ações do conjunto divergem. */
const PRESET_MIXED = "__misto__";

/**
 * As cinco ações que o "Padrão visual da campanha" nivela em um clique (FDD §4 fluxo 3). Não é o
 * registro de ações do servidor (`settings.PRESET_ACTIONS`, que tem mais chaves): é o conjunto
 * que produz a IMAGEM e o MOVIMENTO desta campanha, de ponta a ponta.
 */
export const CAMPAIGN_KINDS = [
  "storyboard.script",
  "storyboard.keyframe",
  "storyboard.angles",
  "motion",
  "base",
] as const;
/** Opcional, pela caixa "aplicar também ao mood board". */
const CAMPAIGN_MOOD_KIND = "mood";

const presetConfigUrl = (pid: string) =>
  `/api/projects/${encodeURIComponent(pid)}/prompter/preset-config`;
export const presetsUrl = (pid: string) => `/api/prompter/presets?pid=${encodeURIComponent(pid)}`;

/** Nome legível de um id de preset (o id cru quando ele saiu do catálogo). */
export function presetLabel(presets: RealismPreset[], id: string | null | undefined): string {
  if (!id) return "sem preset";
  return presets.find((p) => p.id === id)?.name || id;
}

/**
 * Valor do seletor da campanha a partir dos `defaults` resolvidos pelo servidor.
 *
 * "(misto)" é decidido pelo PRESET resolvido, como manda o FDD — não pela camada. Quando as cinco
 * ações resolvem para o MESMO `null`, ainda há dois estados a distinguir, e é aí que a `source`
 * entra: tudo gravado no projeto é "(sem preset)" escolhido; qualquer outra coisa é herança.
 */
function campaignPresetValue(defaults: PresetDefaults): string {
  const entries = CAMPAIGN_KINDS.map((k) => defaults[k]);
  const first = entries[0]?.preset ?? null;
  if (entries.some((e) => (e?.preset ?? null) !== first)) return PRESET_MIXED;
  if (first) return first;
  return entries.every((e) => e?.source === "project") ? PRESET_OFF : PRESET_INHERIT;
}

/**
 * `[extensão]` **Padrão visual da campanha** (card #98, FDD §4 fluxo 3, critério C1).
 *
 * Um seletor que nivela, em um clique, as cinco ações que produzem imagem e movimento da
 * campanha — mais o mood board, opcionalmente. Não há rota nova: as escritas saem pelas
 * `preset-config` que já existiam e nenhuma UI consumia. Escolher um preset dispara um `PUT` por
 * `kind`, em SÉRIE; escolher "(herdar do global)" dispara um `DELETE` por `kind`. Falha parcial
 * não faz retry: ela é reportada citando os `kind` que falharam, e o estado exibido volta a ser
 * o do servidor (`GET /api/prompter/presets?pid=`), nunca o que a tela supôs.
 *
 * O mesmo bloco é montado na etapa 3 (o preset da `base` é uma das cinco ações): a etapa muda só
 * o `id` do DOM, a lógica é esta e não tem cópia.
 */
export function CampaignPreset({
  api,
  pid,
  toast,
  presets,
  defaults,
  onReload,
  id = "sbCampaignPreset",
}: {
  api: (path: string, opts?: RequestInit) => Promise<unknown>;
  pid: string;
  toast: (msg: string) => void;
  presets: RealismPreset[];
  defaults: PresetDefaults;
  /** Devolve ao dono da tela os `defaults` relidos do servidor depois de gravar. */
  onReload: (d: PresetDefaults) => void;
  id?: string;
}) {
  const [alsoMood, setAlsoMood] = useState(false);
  const [busy, setBusy] = useState(false);
  const value = campaignPresetValue(defaults);
  const mixed = value === PRESET_MIXED;

  const reload = async () => {
    try {
      const r = (await api(presetsUrl(pid))) as { defaults?: PresetDefaults };
      onReload(r.defaults || {});
    } catch {
      /* a leitura falhou: o bloco continua mostrando o último estado conhecido */
    }
  };

  async function apply(v: string) {
    if (!pid || v === PRESET_MIXED) return;
    const kinds: string[] = [...CAMPAIGN_KINDS];
    if (alsoMood) kinds.push(CAMPAIGN_MOOD_KIND);
    const failed: string[] = [];
    setBusy(true);
    for (const kind of kinds) {
      try {
        if (v === PRESET_INHERIT) {
          await api(`${presetConfigUrl(pid)}/${encodeURIComponent(kind)}`, { method: "DELETE" });
        } else {
          await api(presetConfigUrl(pid), {
            method: "PUT",
            body: JSON.stringify({ kind, preset: v === PRESET_OFF ? null : v }),
          });
        }
      } catch {
        failed.push(kind);
      }
    }
    // Sempre relê: mesmo no sucesso é o servidor que diz o que ficou valendo (Risco 4 do FDD).
    await reload();
    setBusy(false);
    if (failed.length)
      toast(`Padrão visual: falhou em ${failed.join(", ")} — o bloco mostra o estado real do servidor.`);
    else if (v === PRESET_INHERIT) toast("Padrão visual da campanha: voltou a herdar do global.");
    else toast(`Padrão visual da campanha: ${presetLabel(presets, v === PRESET_OFF ? null : v)}.`);
  }

  return (
    <section className="panel sb-campaign" id={id}>
      {/* `<style>` que monta/desmonta com o bloco — ele vive em duas telas e não tem folha global */}
      <style>{CAMPAIGN_CSS}</style>
      <div className="panel-head">
        <h3>
          Padrão visual da campanha <span className="ext">[extensão]</span>
        </h3>
        <span className="chip mode sbCampaignSource">{mixed ? "(misto)" : `${CAMPAIGN_KINDS.length} ações`}</span>
      </div>
      <p className="fine sbCampaignHint">
        Um preset de realismo para a campanha inteira: roteiro, keyframe, ângulos, movimento e
        imagem base. Ele vale como padrão — cada foto pode fugir dele no seletor da própria linha.
      </p>
      <div className="row wrap">
        <label className="field sb-realism">
          <span className="eyebrow lbl">preset de realismo</span>
          <select
            className="sbCampaignPresetSel"
            aria-label="Padrão visual da campanha (extensão)"
            disabled={busy}
            value={value}
            onChange={(e) => void apply(e.target.value)}
          >
            {mixed ? (
              <option value={PRESET_MIXED}>(misto)</option>
            ) : null}
            <option value={PRESET_INHERIT}>(herdar do global)</option>
            <option value={PRESET_OFF}>(sem preset)</option>
            {presets.map((p) => (
              <option key={p.id} value={p.id} title={p.desc_pt}>
                {`${p.name} — ${p.desc_pt}`}
              </option>
            ))}
          </select>
        </label>
        <label className="sb-campaign-mood">
          <input
            type="checkbox"
            className="sbCampaignMood"
            checked={alsoMood}
            onChange={(e) => setAlsoMood(e.target.checked)}
          />{" "}
          aplicar também ao mood board
        </label>
      </div>
    </section>
  );
}

const CAMPAIGN_CSS = `
  .sb-campaign .sbCampaignHint{margin:2px 0 10px}
  .sb-campaign .sb-realism{flex:1 1 320px}
  .sb-campaign-mood{display:flex;align-items:center;gap:6px;font-size:12px;
    color:var(--ink-row);white-space:nowrap}
`;
