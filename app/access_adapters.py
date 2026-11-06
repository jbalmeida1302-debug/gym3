"""Contrato comum para adaptadores de fabricantes de controle de acesso.
A compatibilidade depende de API/SDK, firmware e modo online de cada equipamento.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

@dataclass
class AccessEvent:
    external_user_id: str
    occurred_at: datetime
    result: str
    device_name: str
    reason: str = ""
    external_event_id: Optional[str] = None

class AccessControlAdapter(Protocol):
    def test_connection(self) -> bool: ...
    def enroll_face(self, student_id: int, name: str): ...
    def set_access_permission(self, external_user_id: str, allowed: bool, reason: str): ...
    def fetch_events(self, since: datetime): ...

def normalize_result(value):
    value = str(value or "").strip().lower()
    if value in {"granted", "allow", "allowed", "success", "authorized", "autorizado", "1", "true"}:
        return "autorizado"
    if value in {"denied", "deny", "blocked", "failed", "unauthorized", "negado", "0", "false"}:
        return "negado"
    return "pendente"
