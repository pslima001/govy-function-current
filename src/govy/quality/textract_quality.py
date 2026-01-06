# src/govy/quality/textract_quality.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class QualityDecision:
    """
    Decisão objetiva sobre a qualidade do output do Textract (camada 1).

    ok:
      - True  => segue pipeline normal (Textract-first)
      - False => caso extremo: habilita fallback (Reducto)
    """
    ok: bool
    reasons: List[str]
    metrics: Dict[str, Any]


def _weird_ratio(text: str, sample_chars: int = 200000) -> float:
    """
    Mede a taxa de caracteres "estranhos" (nem alfanumérico, nem espaços, nem pontuação comum).
    Usa apenas uma amostra inicial do texto para ser rápido.

    Exemplo bom (seu caso): ~0.0021 (0.21%)
    """
    if not text:
        return 1.0

    sample = text[:sample_chars]
    weird = re.findall(r"[^\w\s\.\,\;\:\-\(\)\/\%\$\@\#\&\+\=\?\!]", sample, flags=re.UNICODE)
    return len(weird) / max(1, len(sample))


def evaluate_textract_quality(
    text: str,
    meta: Dict[str, Any] | None = None,
    *,
    # Limiar calibrado para editais típicos e usando seu exemplo bom como referência.
    # Ajustamos conforme você testar mais editais.
    min_chars: int = 80000,
    min_lines: int = 4000,
    max_weird_ratio: float = 0.02,   # 2% (seu bom foi 0.21%)
    allow_garbled_flag: bool = False,
) -> QualityDecision:
    """
    Decide se o texto do Textract é "bom o suficiente" para seguir sem fallback.

    Falha (ok=False) quando:
      - texto muito curto
      - poucas linhas
      - garbled_flag=True (se allow_garbled_flag=False)
      - weird_ratio acima do limiar

    Retorna também metrics para auditoria/log.
    """
    meta = meta or {}
    reasons: List[str] = []

    n_chars = int(meta.get("n_chars_text") or len(text or ""))
    n_lines = int(meta.get("n_lines") or 0)
    garbled_flag = bool(meta.get("garbled_flag", False))

    # se o reader já colocou weird_ratio no meta, usa; senão calcula
    weird_ratio = float(meta.get("weird_ratio")) if meta.get("weird_ratio") is not None else _weird_ratio(text)

    # Regras
    if n_chars < min_chars:
        reasons.append(f"Texto muito curto (chars={n_chars} < {min_chars})")

    # n_lines pode vir 0 se o meta não foi preenchido corretamente;
    # nesse caso, a regra de linhas não deve punir.
    if n_lines and n_lines < min_lines:
        reasons.append(f"Poucas linhas (lines={n_lines} < {min_lines})")

    if (not allow_garbled_flag) and garbled_flag:
        reasons.append("Flag de texto corrompido acionada (garbled_flag=True)")

    if weird_ratio > max_weird_ratio:
        reasons.append(f"Taxa de caracteres estranhos alta (weird_ratio={weird_ratio:.4f} > {max_weird_ratio})")

    metrics = {
        "n_chars": n_chars,
        "n_lines": n_lines,
        "garbled_flag": garbled_flag,
        "weird_ratio": round(weird_ratio, 6),
        "thresholds": {
            "min_chars": min_chars,
            "min_lines": min_lines,
            "max_weird_ratio": max_weird_ratio,
            "allow_garbled_flag": allow_garbled_flag,
        },
    }

    ok = len(reasons) == 0
    return QualityDecision(ok=ok, reasons=reasons, metrics=metrics)

