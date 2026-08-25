from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ShiftSummary:
    shift_id: int
    operator_id: int
    gate_number: int
    started_at: datetime
    ended_at: datetime | None
    total_sessions: int
    completed_sessions: int
    lost_card_sessions: int
    active_sessions: int
    computed_total_piastres: int
    closing_cash_piastres: int | None
    discrepancy_piastres: int | None

__all__ = ["ShiftSummary"]
