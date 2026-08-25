#!/usr/bin/env bash
# Regenera as fixtures de áudio da coleção Postman da etapa 7 (music).
# Precisa de ffmpeg no PATH (o Studio usa o estático de ~/.local/bin).
# As duas primeiras são versionadas; a de 26 MB não é (ver .gitignore).
set -euo pipefail
cd "$(dirname "$0")"

# clique sintético de 120 bpm, 12 s — sustenta o critério da seção 9 do FDD (erro <= 3 bpm).
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=1000:duration=0.04" \
  -f lavfi -i "anullsrc=r=44100:cl=mono:d=0.46" \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1,aloop=loop=23:size=22050,atrim=0:12,asetpts=N/SR/TB" \
  -ar 44100 -ac 1 click-120bpm.wav

# segunda candidata, timbre e andamento diferentes (sha12 diferente) — sustenta a troca de trilha.
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=440:duration=0.04" \
  -f lavfi -i "anullsrc=r=44100:cl=mono:d=0.35" \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1,aloop=loop=25:size=17199,atrim=0:10,asetpts=N/SR/TB" \
  -ar 44100 -ac 1 click-154bpm.wav

# arquivo fora de MEDIA_EXT["audio"] — o import deve ignorar sem erro HTTP.
printf 'nao sou audio\n' > nao-audio.txt

# pasta isolada varrida por import/downloads: 1 wav que NAO entra pelo upload,
# para o request provar `added: 1` (criterio da secao 9 do FDD) de forma deterministica.
mkdir -p downloads-scan
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=660:duration=0.05" \
  -f lavfi -i "anullsrc=r=44100:cl=mono:d=0.45" \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1,aloop=loop=11:size=22050,atrim=0:6,asetpts=N/SR/TB" \
  -ar 44100 -ac 1 downloads-scan/from-downloads.wav

# 26 MB > MAX_UPLOAD_BYTES (25 MB) — sustenta o 413. Nao versionado.
ffmpeg -y -loglevel error -f lavfi -i "anullsrc=r=44100:cl=stereo:d=155" \
  -c:a pcm_s16le oversize-26mb.wav

# O request de import/downloads varre uma pasta ABSOLUTA (o default do serviço é a pasta
# Downloads real do usuário, que um teste não pode tocar). O caminho muda por máquina e por
# worktree, então sai numa CÓPIA local do environment (ignorada pelo git) e o arquivo versionado
# continua portátil. É esse .local.json que o newman deve receber no -e.
python3 -c "import json,sys,pathlib; src=pathlib.Path('../music.postman_environment.json'); dst=pathlib.Path('../music.postman_environment.local.json'); d=json.loads(src.read_text()); d['name']=d['name']+' (local)'; [v.__setitem__('value', sys.argv[1]) for v in d['values'] if v['key']=='downloadsFolder']; dst.write_text(json.dumps(d, ensure_ascii=False, indent=2)+chr(10)); print('environment local:', dst.resolve())" "$PWD/downloads-scan"

ls -la ./*.wav ./nao-audio.txt ./downloads-scan/*.wav
