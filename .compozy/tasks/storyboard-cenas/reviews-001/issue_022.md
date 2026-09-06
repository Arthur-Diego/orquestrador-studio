---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 2022
severity: low
author: claude-code
provider_ref:
---

# Issue 022: Herança do RealismField resolve só motion, não keyframe

## Review Comment

Há um único `preset` por foto, usado em `POST /video-prompt` (ação `motion`) E em `POST /image-prompt` (ação `storyboard.keyframe`), mas o rótulo "(padrão da campanha: X)" resolve só `motion` (`inheritedPreset(MOTION_ACTION)`). Quando o `CampaignPreset` mostra "(misto)" — ou quando alguém grava `preset-config` por fora do bloco — o rótulo afirma um preset que não é o que o `/image-prompt` receberá do servidor. É o cenário que o Risco 4 tenta evitar.

**Correção:** rotular sem o "X" quando `inheritedPreset("storyboard.keyframe") !== inheritedPreset("motion")`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
