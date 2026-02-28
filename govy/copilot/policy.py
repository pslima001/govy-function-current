# govy/copilot/policy.py
"""
Policy Engine — regras que NUNCA podem ser quebradas.

- Sem doutrina
- Sem fontes externas
- Sem geração de defesa
- Sempre exigir evidência interna
- BI desabilitado por padrão (BI_ENABLED=false)
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Policy:
    allow_external_sources: bool = False
    allow_doctrine: bool = False
    allow_defense_generation: bool = False
    require_evidence: bool = True
    max_evidence: int = 4
    allowed_doc_types: List[str] = field(default_factory=list)
    bi_enabled: bool = False


def build_policy() -> Policy:
    """Constrói a policy padrão do copiloto. Nunca doutrina. Nunca externo."""
    bi_enabled = os.environ.get("BI_ENABLED", "false").lower() in ("true", "1", "yes")
    return Policy(
        allow_external_sources=False,
        allow_doctrine=False,
        allow_defense_generation=False,
        require_evidence=True,
        max_evidence=4,
        allowed_doc_types=["lei", "jurisprudencia", "guia_tcu"],
        bi_enabled=bi_enabled,
    )


# ─── Validação pós-resposta ─────────────────────────────────────────

_DOCTRINE_LEAK_PATTERNS = [
    "doutrina",
    "doutrinador",
    "autor ",
    "segundo o professor",
    "na obra ",
    "livro ",
]

_EXTERNAL_SOURCE_PATTERNS = [
    "fonte externa",
    "segundo a internet",
    "de acordo com site",
    "wikipedia",
    "google",
]

_DEFENSE_TONE_PATTERNS = [
    "deveria impugnar",
    "recomendo recorrer",
    "sugiro interpor",
    "apresentar defesa",
    "peça recursal",
    "modelo de recurso",
    "minutar",
]


def validate_response(answer: str, policy: Policy) -> List[str]:
    """
    Valida a resposta gerada pelo LLM contra a policy.
    Retorna lista de violações encontradas (vazia = OK).
    """
    violations = []
    lower = answer.lower()

    if not policy.allow_doctrine:
        for p in _DOCTRINE_LEAK_PATTERNS:
            if p in lower:
                violations.append(f"doctrine_leak:{p}")
                break

    if not policy.allow_external_sources:
        for p in _EXTERNAL_SOURCE_PATTERNS:
            if p in lower:
                violations.append(f"external_source:{p}")
                break

    if not policy.allow_defense_generation:
        for p in _DEFENSE_TONE_PATTERNS:
            if p in lower:
                violations.append(f"defense_tone:{p}")
                break

    return violations
