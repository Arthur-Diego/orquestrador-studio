// Modais do shell (wizard, edição, resets) — Wave 10 · E3 (card [REACT-04]).
//
// Equivalentes de `openWizard`/`openEdit`/`confirmResetStep`/`confirmResetCampaign` de
// `studio/web/app.js`, sobre o `Modal` da E2. Ids/classes são contrato de `shell.py` (recon §3.1):
// `#cfName`, `#cfProduct`, `label:has(input[name=aspect][value='9:16'])`, `button[type=submit]`,
// `.reset-list`, `.modal-actions button.primary`. Os TEXTOS são conteúdo de aula (ADR-004).
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Modal } from "../ui";
import { chaves, useCreateProject, usePatchProject, useResetCampaign, useResetStep } from "../api";
import type { Project } from "../api";
import { ASPECTS } from "./constants";
import { toast } from "./toast";

// ---------- formulário de campanha (wizard e edição) ----------

function CampoFormato({ atual, onPick }: { atual: string; onPick: (id: string) => void }) {
  return (
    <div className="field fmt-field">
      <span className="eyebrow">Formato — pela plataforma de destino</span>
      <div className="fmt">
        {ASPECTS.map((a) => (
          <label key={a.id}>
            <span className="box">
              <i style={{ width: `${a.w}px`, height: `${a.h}px` }} />
            </span>
            <input
              type="radio"
              name="aspect"
              value={a.id}
              checked={a.id === atual}
              onChange={() => onPick(a.id)}
            />
            <span className="ratio">{a.id}</span>
            <span className="dest">{a.dest}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

interface DadosCampanha {
  name: string;
  product: string;
  vibe: string;
  aspect_ratio: string;
}

function CampanhaModal({
  title,
  subtitle,
  submitLabel,
  inicial,
  onClose,
  onSubmit,
}: {
  title: string;
  subtitle: string;
  submitLabel: string;
  inicial: Partial<Project>;
  onClose: () => void;
  onSubmit: (dados: DadosCampanha) => Promise<void>;
}) {
  const [name, setName] = useState(inicial.name ?? "");
  const [product, setProduct] = useState(inicial.product ?? "");
  const [vibe, setVibe] = useState(inicial.vibe ?? "");
  const [aspect, setAspect] = useState(inicial.aspect_ratio ?? "16:9");
  const [loading, setLoading] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const nm = name.trim();
    if (!nm) {
      toast("Dê um nome à campanha");
      nameRef.current?.focus();
      return;
    }
    setLoading(true);
    try {
      await onSubmit({ name: nm, product: product.trim(), vibe: vibe.trim(), aspect_ratio: aspect });
    } catch (err) {
      toast((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title={title} subtitle={subtitle} onClose={onClose}>
      <form id="campForm" noValidate onSubmit={submit}>
        <label className="field" htmlFor="cfName">
          <span className="eyebrow">Nome da campanha</span>
          <input
            id="cfName"
            name="name"
            required
            maxLength={80}
            placeholder="ex.: Gelo Zero"
            ref={nameRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="field" htmlFor="cfProduct">
          <span className="eyebrow">Produto</span>
          <input
            id="cfProduct"
            name="product"
            placeholder="ex.: energy drink (vale em inglês — os prompts são em inglês)"
            value={product}
            onChange={(e) => setProduct(e.target.value)}
          />
        </label>
        <label className="field" htmlFor="cfVibe">
          <span className="eyebrow">Vibe — opcional, encontrada na etapa 2</span>
          <input
            id="cfVibe"
            name="vibe"
            placeholder="(dá para começar sem nenhuma ideia)"
            value={vibe}
            onChange={(e) => setVibe(e.target.value)}
          />
        </label>
        <CampoFormato atual={aspect} onPick={setAspect} />
        <div className="modal-actions">
          <button type="button" className="ghost lg" data-close onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={`primary lg${loading ? " loading" : ""}`} disabled={loading}>
            {submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** `openWizard` — cria a campanha (POST) + aplica o formato (PATCH), como o vanilla. */
export function WizardModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (pid: string) => void;
}) {
  const qc = useQueryClient();
  const criar = useCreateProject();
  const patch = usePatchProject();
  return (
    <CampanhaModal
      title="Nova campanha"
      subtitle="O básico para começar a etapa 1 — o resto o Studio descobre no caminho."
      submitLabel="Criar campanha"
      inicial={{}}
      onClose={onClose}
      onSubmit={async (d) => {
        const p = await criar.mutateAsync({ name: d.name, product: d.product, vibe: d.vibe });
        // O formato vive em project.json e é aplicado por PATCH (a criação não recebe o campo).
        await patch.mutateAsync({ pid: p.id, campos: { aspect_ratio: d.aspect_ratio } }).catch(() => null);
        await qc.refetchQueries({ queryKey: chaves.projetos(), exact: true });
        onClose();
        toast(`Campanha ${p.name} criada`);
        onCreated(p.id);
      }}
    />
  );
}

/** `openEdit` — muda só os dados da campanha; os artefatos já produzidos ficam onde estão. */
export function EditModal({ pid, atual, onClose }: { pid: string; atual: Project; onClose: () => void }) {
  const qc = useQueryClient();
  const patch = usePatchProject();
  return (
    <CampanhaModal
      title="Editar campanha"
      subtitle={`Muda só os dados da campanha — os artefatos já produzidos ficam onde estão (${pid}).`}
      submitLabel="Salvar alterações"
      inicial={atual}
      onClose={onClose}
      onSubmit={async (d) => {
        await patch.mutateAsync({ pid, campos: d });
        await qc.refetchQueries({ queryKey: chaves.projetos(), exact: true });
        await qc.refetchQueries({ queryKey: chaves.projeto(pid), exact: true });
        onClose();
        toast("Campanha atualizada");
      }}
    />
  );
}

// ---------- resets [extensão] (ADR-004: não é passo do curso) ----------

interface EtapaResumo {
  n: number;
  title: string;
  id: string;
}

/** `confirmResetStep` — lista a etapa + as seguintes (cascata) e reseta só após confirmar. */
export function ResetStepModal({
  pid,
  stepId,
  cascata,
  onClose,
  onDone,
}: {
  pid: string;
  stepId: string;
  cascata: readonly EtapaResumo[];
  onClose: () => void;
  onDone: () => void;
}) {
  const reset = useResetStep();
  const alvo = cascata[0];
  const confirmar = async () => {
    try {
      await reset.mutateAsync({ pid, step: stepId });
      onClose();
      toast("Etapa resetada");
      onDone();
    } catch (err) {
      toast((err as Error).message);
    }
  };
  return (
    <Modal
      title={`Resetar etapa ${alvo ? `${alvo.n} — ${alvo.title}` : stepId} [extensão]`}
      subtitle="Extensão do Studio"
      onClose={onClose}
    >
      <p>Isto apaga, em cascata, tudo o que estas etapas produziram:</p>
      <ul className="reset-list">
        {cascata.map((x) => (
          <li key={x.id}>
            <b>
              {x.n}. {x.title}
            </b>
          </li>
        ))}
      </ul>
      <p>
        O <b>nome</b>, o <b>produto</b>, a <b>vibe</b> e o <b>formato</b> da campanha são mantidos.
      </p>
      <p className="reset-note">Reset é uma extensão do Studio, não um passo do curso.</p>
      <div className="modal-actions">
        <button type="button" className="ghost lg" data-close onClick={onClose}>
          Cancelar
        </button>
        <button type="button" className="primary lg danger" data-act="1" onClick={confirmar}>
          Resetar
        </button>
      </div>
    </Modal>
  );
}

/** `confirmResetCampaign` — reset da campanha inteira (visão geral). */
export function ResetCampaignModal({
  pid,
  onClose,
  onDone,
}: {
  pid: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const reset = useResetCampaign();
  const confirmar = async () => {
    try {
      await reset.mutateAsync({ pid });
      onClose();
      toast("Campanha resetada");
      onDone();
    } catch (err) {
      toast((err as Error).message);
    }
  };
  return (
    <Modal title="Resetar campanha [extensão]" subtitle="Extensão do Studio" onClose={onClose}>
      <p>
        Isto apaga tudo o que as 10 etapas produziram — referências, mood board, imagem base,
        storyboard (cenas e ângulos), takes, trilha, montagem, export, publicação e prospecção.
      </p>
      <p>
        O <b>nome</b>, o <b>produto</b>, a <b>vibe</b> e o <b>formato</b> da campanha são mantidos.
      </p>
      <p className="reset-note">Reset é uma extensão do Studio, não um passo do curso.</p>
      <div className="modal-actions">
        <button type="button" className="ghost lg" data-close onClick={onClose}>
          Cancelar
        </button>
        <button type="button" className="primary lg danger" data-act="1" onClick={confirmar}>
          Resetar campanha
        </button>
      </div>
    </Modal>
  );
}
