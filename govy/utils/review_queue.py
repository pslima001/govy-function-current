"""
GOVY - Fila de RevisÃ£o para JurÃ­dico
SPEC 1.2 - Knowledge Base JurÃ­dica

Tudo que nÃ£o auto-aprovar:
- vai para kb_review_queue/
- jurÃ­dico confirma ou corrige
- depois chama /upsert
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .juris_constants import REVIEW_QUEUE_DIR

logger = logging.getLogger(__name__)


class ReviewQueue:
    """Gerencia fila de revisÃ£o para o jurÃ­dico."""
    
    def __init__(self, queue_dir: str = None):
        self.queue_dir = Path(queue_dir or REVIEW_QUEUE_DIR)
        self._ensure_dir()
    
    def _ensure_dir(self):
        """Cria diretÃ³rio se nÃ£o existir."""
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # SubdiretÃ³rios para organizaÃ§Ã£o
        (self.queue_dir / "pending").mkdir(exist_ok=True)
        (self.queue_dir / "approved").mkdir(exist_ok=True)
        (self.queue_dir / "rejected").mkdir(exist_ok=True)
    
    def add_to_queue(self, result: Dict[str, Any]) -> str:
        """
        Adiciona item Ã  fila de revisÃ£o.
        
        Args:
            result: Resultado do pipeline (com chunks, audit, etc)
            
        Returns:
            item_id do item na fila
        """
        item_id = result.get("process_id", datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        
        queue_item = {
            "item_id": item_id,
            "title": result.get("title"),
            "citation_base": result.get("citation_base"),
            "doc_meta": result.get("doc_meta"),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending",
            
            # Dados para revisÃ£o
            "chunks_proposed": result.get("chunks", []),
            "meta_proposed": result.get("meta", {}),
            
            # Auditoria
            "extraction_raw": result.get("extraction_raw"),
            "audit_raw": result.get("audit_raw"),
            "review_reason": result.get("review_reason"),
            
            # Campos que precisam de atenÃ§Ã£o
            "fields_to_review": self._identify_fields_to_review(result),
        }
        
        # Salva arquivo
        filepath = self.queue_dir / "pending" / f"{item_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(queue_item, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Item adicionado Ã  fila: {item_id} ({filepath})")
        
        return item_id
    
    def _identify_fields_to_review(self, result: Dict) -> List[str]:
        """Identifica campos que precisam de revisÃ£o."""
        fields = []
        
        audit = result.get("audit_raw", {})
        
        for audit_item in audit.get("audits", []):
            # Campo com discordÃ¢ncia
            if not audit_item.get("agree"):
                fields.append(audit_item.get("campo"))
            # Campo com confianÃ§a baixa
            elif audit_item.get("confidence", 1.0) < 0.90:
                fields.append(audit_item.get("campo"))
        
        return list(set(fields))
    
    def list_pending(self) -> List[Dict]:
        """Lista itens pendentes de revisÃ£o."""
        items = []
        
        pending_dir = self.queue_dir / "pending"
        for filepath in pending_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    item = json.load(f)
                    items.append({
                        "item_id": item.get("item_id"),
                        "title": item.get("title"),
                        "timestamp": item.get("timestamp"),
                        "review_reason": item.get("review_reason"),
                        "fields_to_review": item.get("fields_to_review"),
                    })
            except Exception as e:
                logger.error(f"Erro ao ler {filepath}: {e}")
        
        # Ordena por timestamp (mais antigos primeiro)
        items.sort(key=lambda x: x.get("timestamp", ""))
        
        return items
    
    def get_item(self, item_id: str) -> Optional[Dict]:
        """ObtÃ©m item completo da fila."""
        filepath = self.queue_dir / "pending" / f"{item_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def approve_item(self, item_id: str, corrections: Optional[Dict] = None) -> Dict:
        """
        Aprova item (opcionalmente com correÃ§Ãµes).
        
        Args:
            item_id: ID do item
            corrections: Dict com correÃ§Ãµes (campo -> novo_valor)
            
        Returns:
            Item aprovado pronto para indexaÃ§Ã£o
        """
        filepath = self.queue_dir / "pending" / f"{item_id}.json"
        
        if not filepath.exists():
            raise ValueError(f"Item nÃ£o encontrado: {item_id}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            item = json.load(f)
        
        # Aplica correÃ§Ãµes se houver
        if corrections:
            for chunk in item.get("chunks_proposed", []):
                for campo, valor in corrections.items():
                    if campo in chunk:
                        chunk[campo] = valor
            
            for campo, valor in corrections.items():
                if campo in item.get("meta_proposed", {}):
                    item["meta_proposed"][campo] = valor
        
        # Atualiza status
        item["status"] = "approved"
        item["approved_at"] = datetime.utcnow().isoformat()
        item["corrections_applied"] = corrections
        
        # Move para approved
        new_filepath = self.queue_dir / "approved" / f"{item_id}.json"
        with open(new_filepath, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        
        # Remove do pending
        filepath.unlink()
        
        logger.info(f"Item aprovado: {item_id}")
        
        return item
    
    def reject_item(self, item_id: str, reason: str) -> Dict:
        """Rejeita item."""
        filepath = self.queue_dir / "pending" / f"{item_id}.json"
        
        if not filepath.exists():
            raise ValueError(f"Item nÃ£o encontrado: {item_id}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            item = json.load(f)
        
        # Atualiza status
        item["status"] = "rejected"
        item["rejected_at"] = datetime.utcnow().isoformat()
        item["rejection_reason"] = reason
        
        # Move para rejected
        new_filepath = self.queue_dir / "rejected" / f"{item_id}.json"
        with open(new_filepath, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        
        # Remove do pending
        filepath.unlink()
        
        logger.info(f"Item rejeitado: {item_id} - {reason}")
        
        return item
    
    def get_stats(self) -> Dict:
        """Retorna estatÃ­sticas da fila."""
        return {
            "pending": len(list((self.queue_dir / "pending").glob("*.json"))),
            "approved": len(list((self.queue_dir / "approved").glob("*.json"))),
            "rejected": len(list((self.queue_dir / "rejected").glob("*.json"))),
        }


# InstÃ¢ncia global
review_queue = ReviewQueue()
