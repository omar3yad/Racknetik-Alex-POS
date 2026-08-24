from datetime import datetime
from pydantic import BaseModel, ConfigDict

class AuditLogResponse(BaseModel):
    id: int
    actor_id: int
    action: str
    entity_type: str
    entity_id: int
    payload_before: str | None
    payload_after: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
