from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


# Fallback seguro: se patterns.json não estiver disponível, não quebrar os extractors.
_DEFAULT_PATTERNS: Dict[str, Any] = {"extractors": {}}


def _candidate_paths() -> list[Path]:
    """
    Paths candidatos para patterns.json.

    Observação importante:
    - Em Azure Functions (Linux), o código fica em /home/site/wwwroot/...
    - Localmente, o path relativo ao próprio arquivo (este módulo) é o mais confiável.
    """
    here = Path(__file__).resolve()
    local_path = here.parent / "patterns.json"

    azure_path = Path("/home/site/wwwroot/govy/extractors/config/patterns.json")

    # Útil para execução via scripts com cwd no root do repo
    cwd_path = Path.cwd() / "govy" / "extractors" / "config" / "patterns.json"

    # Ordem importa
    return [local_path, azure_path, cwd_path]


def _read_json(path: Path) -> Dict[str, Any]:
    # patterns.json atual vem com UTF-8 BOM, então usamos utf-8-sig.
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else dict(_DEFAULT_PATTERNS)


@lru_cache(maxsize=1)
def load_patterns() -> Dict[str, Any]:
    """
    Carrega patterns.json com cache (1x por processo).

    Regras:
    - Se GOVY_PATTERNS_PATH estiver setado, usa esse path primeiro.
    - Caso falhe, tenta paths candidatos.
    - Em qualquer falha, retorna fallback seguro.
    """
    override = os.getenv("GOVY_PATTERNS_PATH")
    if override:
        try:
            p = Path(override).expanduser().resolve()
            if p.exists():
                return _read_json(p)
        except Exception:
            return dict(_DEFAULT_PATTERNS)

    for p in _candidate_paths():
        try:
            if p.exists():
                return _read_json(p)
        except Exception:
            continue

    return dict(_DEFAULT_PATTERNS)


def get_extractor_config(extractor_id: str) -> Dict[str, Any]:
    """
    Retorna a config do extractor (dict). Se não existir, retorna {}.

    Exemplo:
        cfg = get_extractor_config("e001_entrega")
        positivos = cfg.get("contexto", {}).get("positivos", [...defaults...])
    """
    patterns = load_patterns()
    extractors = patterns.get("extractors", {})
    if not isinstance(extractors, dict):
        return {}
    cfg = extractors.get(extractor_id, {})
    return cfg if isinstance(cfg, dict) else {}
