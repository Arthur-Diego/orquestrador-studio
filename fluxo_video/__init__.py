"""[extensão] fluxo_video — fluxo LOCAL e independente de criação de vídeo.

roteiro → cenas → planos (JSON congruente) → imagens → vídeo. Autossuficiente: usa o
`local_ai_engine` (no lugar, via binário) para as imagens e o ffmpeg para o vídeo. NÃO depende
do ContentFlow nem de nenhum serviço externo. Área independente do núcleo do curso (ADR-010):
não toca `studio/{app.py,steps.py,higgsfield.py}` nem `frontend/`.

Camadas:
- `schema`       — modelos Pydantic do roteiro rico (RoteiroPro v1.0) — fonte da verdade do formato.
- `validador`    — congruência entre campos (o "total sentido").
- `engine_local` — ponte fina para o local_ai_engine (gera imagem via ComfyUI).
- `render`       — montagem de vídeo com ffmpeg (Ken Burns + concat).
- `projeto`      — pasta de saída (`projects/<slug>/`).
- `pipeline`     — orquestra roteiro → imagens → vídeo.
- `cli`          — comandos (validar/imagens/video/tudo).
"""

from .schema import Roteiro, carregar_roteiro
from .validador import RelatorioValidacao, validar_congruencia

__all__ = ["Roteiro", "carregar_roteiro", "validar_congruencia", "RelatorioValidacao"]
