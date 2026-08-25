from datetime import datetime
from pydantic import BaseModel

class ReceiptData(BaseModel):
    session_id: int
    card_code: str
    plate_number: str | None
    gate_number: int
    operator_name: str
    entry_time: datetime
    exit_time: datetime
    duration_minutes: int
    duration_display: str
    pricing_rule_label: str
    rate_per_hour: int
    grace_period_mins: int
    base_amount: int
    penalty_amount: int
    total_amount: int
    total_display: str
    payment_method: str
    is_lost_card: bool
    is_grace_period: bool
    garage_name: str

__all__ = ["ReceiptData"]
