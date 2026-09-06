// Área global "Personagens" (ADR-039) — biblioteca de identidade reutilizável entre campanhas.
//
// Fluxo: criar → explorar variações no motor local (grátis) → FIXAR o escolhido (gera o descritor
// canônico) → character sheet → aplicar à campanha (o descritor reancora os prompts das etapas
// 3–5). Reusa as classes do design system compartilhado (nenhuma folha nova).
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../api";
import { useShell } from "../../shell/context";

interface Character {
  id: string;
  name: string;
  style: string;
  descriptor?: string;
  locked_ref?: string | null;
  sheet?: string[];
  providers?: Record<string, unknown>;
}
interface Candidate {
  id: string;
  thumb?: string;
  file: string;
  view?: string;
}
interface Job {
  state: string;
  done: number;
  total: number;
  added: number;
  error?: string | null;
  mode?: string | null;
}

export interface CharactersAreaProps {
  pid: string | null;
  refreshKey?: number;
}

export function CharactersArea({ pid, refreshKey = 0 }: CharactersAreaProps) {
  const [chars, setChars] = useState<Character[]>([]);
  const [selId, setSelId] = useState<string | null>(null);

  const recarregar = useCallback(async () => {
    setChars((await api("/api/characters").catch(() => [])) as Character[]);
  }, []);
  useEffect(() => {
    void recarregar();
  }, [recarregar, refreshKey]);

  if (selId) return <CharacterDetail cid={selId} pid={pid} onBack={() => { setSelId(null); void recarregar(); }} />;

  return (
    <div className="panel">
      <header className="stephead">
        <span className="eyebrow">Biblioteca · [extensão]</span>
        <h2>Personagens</h2>
        <p className="lede">Acerte a identidade uma vez e reaplique em qualquer campanha, foto e vídeo.</p>
      </header>
      <NewCharacter onCreated={(c) => { void recarregar(); setSelId(c.id); }} />
      {chars.length === 0 ? (
        <p className="note">Nenhum personagem ainda. Crie o primeiro acima.</p>
      ) : (
        <div className="gallery">
          {chars.map((c) => (
            <button key={c.id} className="card" type="button" onClick={() => setSelId(c.id)} style={{ textAlign: "left" }}>
              {c.locked_ref ? (
                <img className="thumb" src={`/cfiles/${c.id}/${c.locked_ref}`} alt={c.name} />
              ) : (
                <div className="thumb none"><span className="empty">sem foto fixada</span></div>
              )}
              <div style={{ padding: "6px 2px" }}>
                <b>{c.name}</b>{" "}
                <span className={`chip ${c.locked_ref ? "ok" : "todo"}`}>{c.locked_ref ? "fixado" : "a fixar"}</span>
                <div className="fine">{c.style}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NewCharacter({ onCreated }: { onCreated: (c: Character) => void }) {
  const [name, setName] = useState("");
  const [style, setStyle] = useState("foto");
  const criar = async () => {
    if (!name.trim()) return;
    const c = (await api("/api/characters", { method: "POST", body: JSON.stringify({ name, style }) })) as Character;
    setName("");
    onCreated(c);
  };
  return (
    <div className="row wrap" style={{ gap: 8, alignItems: "flex-end", margin: "8px 0 16px" }}>
      <label className="field">
        <span className="eyebrow sm">Nome</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: Eden" />
      </label>
      <label className="field">
        <span className="eyebrow sm">Estilo</span>
        <select value={style} onChange={(e) => setStyle(e.target.value)}>
          <option value="foto">foto</option>
          <option value="anime">anime</option>
          <option value="3d">3d</option>
        </select>
      </label>
      <button className="primary" type="button" onClick={criar} disabled={!name.trim()}>
        Novo personagem
      </button>
    </div>
  );
}

function CharacterDetail({ cid, pid, onBack }: { cid: string; pid: string | null; onBack: () => void }) {
  const { navigate } = useShell();
  const [ch, setCh] = useState<Character | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  const carregar = useCallback(async () => {
    setCh((await api(`/api/characters/${cid}`)) as Character);
    setCands((await api(`/api/characters/${cid}/candidates?step=explore`).catch(() => [])) as Candidate[]);
  }, [cid]);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  // Poll do job enquanto gera (explore/sheet).
  useEffect(() => {
    if (!busy) return;
    timer.current = window.setInterval(async () => {
      const j = (await api(`/api/characters/${cid}/job`).catch(() => null)) as Job | null;
      setJob(j);
      if (j && j.state !== "running") {
        setBusy(false);
        void carregar();
      }
    }, 2000);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [busy, cid, carregar]);

  const explorar = async () => {
    if (!brief.trim()) return;
    await api(`/api/characters/${cid}/explore`, { method: "POST", body: JSON.stringify({ brief, count: 6 }) });
    setBusy(true);
  };
  const fixar = async (candidateId: string) => {
    await api(`/api/characters/${cid}/lock`, { method: "POST", body: JSON.stringify({ candidate_id: candidateId, step: "explore" }) });
    void carregar();
  };
  const gerarSheet = async () => {
    await api(`/api/characters/${cid}/sheet`, { method: "POST", body: JSON.stringify({}) });
    setBusy(true);
  };
  const aplicar = async () => {
    if (!pid) return;
    await api(`/api/projects/${pid}/character`, { method: "POST", body: JSON.stringify({ cid }) });
    navigate("overview");
  };

  if (!ch) return <div className="empty">Carregando…</div>;

  return (
    <div className="panel">
      <button className="link" type="button" onClick={onBack}>← Personagens</button>
      <header className="stephead">
        <span className="eyebrow">Personagem · {ch.style}</span>
        <h2>{ch.name}</h2>
      </header>

      {ch.descriptor ? (
        <div className="strip">
          <b>Descritor de identidade</b>
          <p className="note">{ch.descriptor}</p>
        </div>
      ) : (
        <p className="note">Explore variações e fixe a que você acertou para gerar o descritor de identidade.</p>
      )}

      <div className="row wrap" style={{ gap: 8, alignItems: "flex-end", margin: "12px 0" }}>
        <label className="field grow">
          <span className="eyebrow sm">Brief (inglês)</span>
          <input value={brief} onChange={(e) => setBrief(e.target.value)} placeholder="ex.: young woman, silver hair, dark tech coat" />
        </label>
        <button className="primary" type="button" onClick={explorar} disabled={busy || !brief.trim()}>
          Explorar (grátis)
        </button>
        {ch.descriptor ? (
          <button type="button" onClick={gerarSheet} disabled={busy}>Gerar character sheet</button>
        ) : null}
        {pid ? (
          <button className="cta" type="button" onClick={aplicar} disabled={!ch.descriptor}>Aplicar à campanha</button>
        ) : null}
      </div>

      {busy && job ? <p className="note">{job.mode}: {job.done}/{job.total} ({job.added} gerados)…</p> : null}

      {cands.length > 0 ? (
        <>
          <span className="eyebrow">Variações — clique para fixar</span>
          <div className="gallery sm">
            {cands.map((c) => (
              <button key={c.id} className={`card${ch.locked_ref?.endsWith(c.file) ? " sel" : ""}`} type="button" onClick={() => fixar(c.id)} title="Fixar este">
                {c.thumb ? <img className="thumb" src={`/cfiles/${cid}/explore/candidates/${c.thumb}`} alt="" /> : null}
              </button>
            ))}
          </div>
        </>
      ) : null}

      {ch.sheet && ch.sheet.length > 0 ? (
        <>
          <span className="eyebrow">Character sheet</span>
          <div className="gallery sm">
            {ch.sheet.map((rel) => (
              <img key={rel} className="thumb" src={`/cfiles/${cid}/${rel.replace("/candidates/", "/candidates/thumbs/").replace(/\.png$/, ".jpg")}`} alt="" />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
