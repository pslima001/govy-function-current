# govy/copilot/conversation.py
"""
Memória multi-turno conservadora — guarda últimos N turns por conversation_id.

Storage: Azure Blob Storage (kb-content/copilot/conversations/).
Alternativas futuras: Redis, PostgreSQL.

Não persiste conteúdo sensível além do necessário.
Não "aprende" — apenas mantém contexto do diálogo corrente.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

CONTAINER_NAME = "kb-content"
BLOB_PREFIX = "copilot/conversations"
MAX_TURNS = 10

# ─── In-memory fallback (quando Blob não disponível) ──────────────
# Para dev/testes sem Azure. Em produção usa Blob.
_memory_store: dict[str, list] = {}


class ConversationTurn:
    """Um turno de conversa (user + assistant)."""

    def __init__(
        self,
        role: str,
        content: str,
        intent: str = None,
        timestamp: str = None,
    ):
        self.role = role  # "user" | "assistant"
        self.content = content[:500]  # Truncar para não explodir
        self.intent = intent
        self.timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationTurn":
        return cls(
            role=d["role"],
            content=d["content"],
            intent=d.get("intent"),
            timestamp=d.get("timestamp"),
        )


def _blob_path(conversation_id: str) -> str:
    return f"{BLOB_PREFIX}/{conversation_id}.json"


def get_history(conversation_id: str) -> list[ConversationTurn]:
    """Recupera histórico de conversa (últimos MAX_TURNS turnos)."""
    if not conversation_id:
        return []

    # Tentar Blob Storage
    try:
        from govy.utils.azure_clients import get_container_client

        container = get_container_client(CONTAINER_NAME)
        blob = container.get_blob_client(_blob_path(conversation_id))
        data = json.loads(blob.download_blob().readall().decode("utf-8"))
        turns = [ConversationTurn.from_dict(t) for t in data.get("turns", [])]
        return turns[-MAX_TURNS:]
    except Exception:
        # Fallback: in-memory
        if conversation_id in _memory_store:
            return [ConversationTurn.from_dict(t) for t in _memory_store[conversation_id]][-MAX_TURNS:]
        return []


def save_turn(
    conversation_id: str,
    user_text: str,
    assistant_answer: str,
    intent: str = None,
) -> None:
    """Salva um turno completo (user + assistant) na conversa."""
    if not conversation_id:
        return

    history = get_history(conversation_id)
    history.append(ConversationTurn(role="user", content=user_text, intent=intent))
    history.append(ConversationTurn(role="assistant", content=assistant_answer, intent=intent))

    # Manter só últimos MAX_TURNS
    history = history[-MAX_TURNS:]
    turns_data = [t.to_dict() for t in history]

    # Tentar Blob Storage
    try:
        from govy.utils.azure_clients import get_container_client
        from azure.storage.blob import ContentSettings

        container = get_container_client(CONTAINER_NAME)
        blob = container.get_blob_client(_blob_path(conversation_id))
        payload = json.dumps(
            {"conversation_id": conversation_id, "turns": turns_data},
            ensure_ascii=False,
            indent=2,
        )
        blob.upload_blob(
            payload,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )
        logger.debug(f"conversation [{conversation_id}]: {len(history)} turns salvos em Blob")
    except Exception:
        # Fallback: in-memory
        _memory_store[conversation_id] = turns_data
        logger.debug(f"conversation [{conversation_id}]: {len(history)} turns salvos in-memory")


def build_history_context(conversation_id: str) -> Optional[str]:
    """
    Monta contexto resumido do histórico para o LLM.
    Retorna string formatada ou None se não houver histórico.
    """
    history = get_history(conversation_id)
    if not history:
        return None

    parts = ["CONTEXTO DO DIÁLOGO ANTERIOR:"]
    for turn in history:
        prefix = "Usuário" if turn.role == "user" else "Copiloto"
        parts.append(f"  {prefix}: {turn.content}")
    parts.append("")

    return "\n".join(parts)
