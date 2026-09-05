// Etapa 4 — Storyboard (aulas 010 + 011, ADR-015) — porte React da tela (Wave 10 · E8, card
// [REACT-09]). O plugin é descoberto pelo host da E3 via `import.meta.glob` (nenhum registry
// central). Duas metades na mesma tela, cada uma no seu escopo:
//   - IDEAÇÃO + CENAS EM TEXTO (aula 010) + os `[extensão]` de vídeo por foto (ADR-021/022),
//     inpaint-marcacao (ADR-004) e roteiro por Claude (ADR-025/028) — `Ideation`;
//   - ÂNGULOS POR CENA (aula 011) + cena do produto (aula 013) — `Angles`.
// O guia é único ("storyboard"): as duas metades pedem a mesma atualização por `refreshGuide`.
//
// O ciclo do host: montar = `init`, desmontar = `destroy` (React para os polls dos jobs no cleanup
// dos efeitos), troca de projeto reflete no `bootKey` (`ctx.pid()`) que rebobina as duas metades —
// o `onProject` vestigial do vanilla vira a dependência de efeito.
import { useCallback, useState } from "react";
import { StepGuide } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";
import { Ideation } from "./Ideation";
import { Angles } from "./Angles";

export default function Storyboard() {
  const ctx = useStudio();
  const pid = ctx.pid();

  // Recarrega o painel de guia (remonta o `<StepGuide>`, que rebusca `/guide/storyboard` e avisa o
  // shell por `onGuide`) — o equivalente do `ctx.guide()`/`renderGuide` do vanilla.
  const [guideNonce, setGuideNonce] = useState(0);
  const refreshGuide = useCallback(() => setGuideNonce((n) => n + 1), []);

  // Ordem do vanilla: a metade ÂNGULOS e o guia dependem do `storyboard/scenes.json`, que a metade
  // IDEAÇÃO cria no seu `GET /storyboard/scenes`. Só armamos os ÂNGULOS (via `bootKey`) e reatamos o
  // guia DEPOIS que a IDEAÇÃO sinaliza — reproduzindo `ideation → angles → renderGuide`.
  const [scenesReadyPid, setScenesReadyPid] = useState<string | null>(null);
  const handleScenesReady = useCallback((p: string) => {
    setScenesReadyPid(p);
    setGuideNonce((n) => n + 1); // rebusca o guia com o scenes.json já criado
  }, []);

  return (
    <>
      <header className="stephead">
        <span className="eyebrow">Etapa 4 · aulas 010 + 011</span>
        <h2>Storyboard</h2>
        <p className="lede">
          A imagem base vira história: edite <b>uma instrução por vez</b>, escreva ~5 cenas com
          começo, descoberta, ação e desfecho e, por cena, monte <b>vários ângulos</b> (upload +
          prompt de ângulo, escolha e ordene) — mais a cena do produto.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId="storyboard" pid={pid} onGuide={ctx.onGuide} />
      </section>

      <Ideation ctx={ctx} refreshGuide={refreshGuide} bootKey={pid} onScenesReady={handleScenesReady} />
      <Angles ctx={ctx} refreshGuide={refreshGuide} bootKey={scenesReadyPid} />
    </>
  );
}
