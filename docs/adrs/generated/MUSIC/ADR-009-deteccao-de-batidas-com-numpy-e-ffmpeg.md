# ADR-009: Detecção de batidas com numpy + ffmpeg (sem librosa)

**Status:** Aceito
**Data:** 2026-08-25
**Módulo:** MUSIC
**ADRs relacionados:** [ADR-003](../STUDIO/ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](../STUDIO/ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](../STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md)

## Contexto e problema

A aula 013 manda escolher a trilha antes da montagem e diz que "nas batidas fortes tem que acontecer alguma coisa". A etapa 7 materializa isso em `audio/beats.json` (bpm, batidas, impactos) que a etapa 8 usa para propor cortes. O plano original e a `wave-1.md` previam librosa; librosa traz numba, scipy e scikit-learn (dezenas de MB, compilação e tempo de CI), para um cálculo simples sobre um envelope de energia.

## Decisão

Detectar batidas com **numpy + ffmpeg**: o ffmpeg decodifica a trilha para PCM mono 22050 Hz (arquivo temporário `.f32le`, porque `common/ffmpeg.run` opera em modo texto), o serviço calcula o envelope de energia por janelas (~116 ms de suavização), marca picos acima de `média + k·desvio` como impactos (k padrão 1,5, espaçamento mínimo 0,5 s) e estima o tempo por autocorrelação com prior log-normal em 120 bpm e interpolação parabólica (erro medido ≤ 0,5 bpm entre 90 e 160 bpm). A detecção é síncrona dentro do `select` (trilhas de 30 a 60 s, ~40 ms) — exceção deliberada à ADR-006, que vale para trabalhos longos.

## Alternativas consideradas

1. **librosa** (`beat_track` + `onset_strength`): mais robusta em música complexa; rejeitada pelo peso das dependências e pelo CI.
2. **Marcação manual das batidas na UI**: fiel à aula ("sentir"), mas o instrutor usa as batidas visíveis na forma de onda; a detecção automática é a versão executável disso e continua editável (`k` e recálculo).

## Consequências

- Positivas: `numpy` é a única dependência nova; suíte roda em segundos; sem código nativo.
- Negativas: precisão menor que librosa em trilhas sem transientes claros; o prior de 120 bpm é uma escolha musical (comerciais/trailers) — registrado para revisão se o uso mudar. Quem precisar de precisão maior pode trocar `studio/music/beats.py` sem alterar o contrato `beats.json`.
