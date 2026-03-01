# govy/copilot/config.py
"""
Configuração centralizada do Copiloto — fail-closed.

LLM_ENABLED=false (default): endpoint responde "IA indisponível"
LLM_ENABLED=true: exige env vars obrigatórias ou aborta na inicialização
"""
import os
import logging

logger = logging.getLogger(__name__)

# ─── Switch principal ──────────────────────────────────────────────
LLM_ENABLED = os.environ.get("LLM_ENABLED", "false").lower() in ("true", "1", "yes")

# ─── Provider ──────────────────────────────────────────────────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # anthropic | openai

# ─── Anthropic ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("COPILOT_LLM_MODEL", "claude-sonnet-4-20250514")

# ─── OpenAI ────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-4.1")
OPENAI_TEMPERATURE = float(os.environ.get("OPENAI_TEMPERATURE", "0.2"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "1500"))

# ─── Timeouts e retries (curtos e controlados) ────────────────────
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "1"))

# ─── Mensagem padrão quando IA desligada ──────────────────────────
LLM_DISABLED_MESSAGE = "IA indisponível no momento."


def validate_llm_config() -> tuple:
    """
    Valida configuração obrigatória quando LLM_ENABLED=true.
    Returns: (ok: bool, error_message: str)
    """
    if not LLM_ENABLED:
        logger.info("copilot config: LLM_ENABLED=false — modo fail-closed ativo")
        return True, ""

    if LLM_PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY:
            msg = "LLM_ENABLED=true mas ANTHROPIC_API_KEY não configurada — abortando"
            logger.error(msg)
            return False, msg
        logger.info(f"copilot config: provider=anthropic model={ANTHROPIC_MODEL}")

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            msg = "LLM_ENABLED=true mas OPENAI_API_KEY não configurada — abortando"
            logger.error(msg)
            return False, msg
        logger.info(f"copilot config: provider=openai model={OPENAI_MODEL}")

    else:
        msg = f"LLM_PROVIDER inválido: '{LLM_PROVIDER}' (aceitos: anthropic, openai)"
        logger.error(msg)
        return False, msg

    return True, ""


def get_active_model() -> str:
    """Retorna o modelo ativo conforme provider."""
    if LLM_PROVIDER == "openai":
        return OPENAI_MODEL
    return ANTHROPIC_MODEL


def get_active_api_key() -> str:
    """Retorna a API key ativa conforme provider."""
    if LLM_PROVIDER == "openai":
        return OPENAI_API_KEY
    return ANTHROPIC_API_KEY
