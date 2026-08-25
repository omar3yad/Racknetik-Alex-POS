from datetime import datetime
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.parking_card import ParkingCard, CardStatus
from services.exceptions import (
    InvalidBarcodeFormatError,
    CardNotFoundError,
    CardAlreadyActiveError,
    CardNotAvailableError,
    CardHasNoActiveSessionError,
)

class CardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def normalize_code(self, raw: str) -> str:
        """Strips raw string, uppercases it, and validates format."""
        if not raw:
            raise InvalidBarcodeFormatError("Barcode is empty")
        normalized = raw.strip().upper()
        if not re.match(r"^[A-Z0-9\-_]{1,50}$", normalized):
            raise InvalidBarcodeFormatError(f"Invalid barcode: '{raw[:20]}'")
        return normalized

    async def get_by_code(self, card_code: str) -> ParkingCard:
        """Normalizes card_code, queries database, and returns ParkingCard or raises CardNotFoundError."""
        normalized = self.normalize_code(card_code)
        result = await self.db.execute(
            select(ParkingCard).where(ParkingCard.card_code == normalized).limit(1)
        )
        card = result.scalars().first()
        if not card:
            raise CardNotFoundError(f"Card '{card_code}' not found")
        return card

    async def validate_for_entry(self, card_code: str) -> ParkingCard:
        """Validates that a card is available to open a new entry session."""
        card = await self.get_by_code(card_code)
        if card.status == CardStatus.IN_USE:
            raise CardAlreadyActiveError(f"Card '{card_code}' is already active")
        if card.status in (CardStatus.LOST, CardStatus.DAMAGED):
            raise CardNotAvailableError(f"Card '{card_code}' is {card.status.value}")
        return card

    async def validate_for_exit(self, card_code: str, session_repo: Any) -> Any:
        """Validates that a card has an active session to close on exit."""
        card = await self.get_by_code(card_code)
        session = await session_repo.get_active_by_card_id(card.id)
        if not session:
            raise CardHasNoActiveSessionError(f"Card '{card_code}' has no active session")
        return session

    async def set_status(self, card: ParkingCard, status: CardStatus) -> ParkingCard:
        """Updates the status and last_seen_at timestamp of a card, flushing changes."""
        card.status = status
        card.last_seen_at = datetime.utcnow()
        await self.db.flush()
        return card

__all__ = ["CardService"]
