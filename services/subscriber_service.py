from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from models.subscriber import Subscriber
from repositories.subscriber_repo import SubscriberRepository
from repositories.subscription_repo import SubscriptionRepository
from schemas.subscriptions import SubscriberCreate, SubscriberUpdate
from services.audit_service import AuditService
from services.plate_service import PlateService
from services.exceptions import (
    SubscriberNotFoundError,
    SubscriberPlateAlreadyExistsError,
)
from utils.time import cairo_now


class SubscriberService:
    def __init__(
        self,
        db: AsyncSession,
        subscriber_repo: SubscriberRepository,
        plate_service: PlateService,
        audit_service: AuditService,
    ):
        self.db = db
        self.subscriber_repo = subscriber_repo
        self.plate_service = plate_service
        self.audit_service = audit_service

    async def create_subscriber(
        self, data: SubscriberCreate, admin_id: int
    ) -> Subscriber:
        """Normalizes plate number and creates subscriber after uniqueness check."""
        normalized_plate = self.plate_service.normalize(data.plate_number)
        existing = await self.subscriber_repo.get_by_plate(normalized_plate)
        if existing is not None:
            raise SubscriberPlateAlreadyExistsError(
                f"Subscriber with plate '{normalized_plate}' already exists"
            )

        subscriber = await self.subscriber_repo.create(
            full_name=data.full_name,
            plate_number=normalized_plate,
            phone_number=data.phone_number,
            notes=data.notes,
        )
        await self.db.commit()
        await self.db.refresh(subscriber)

        await self.audit_service.log(
            actor_id=admin_id,
            action="SUBSCRIBER_CREATED",
            entity_type="subscriber",
            entity_id=subscriber.id,
            before=None,
            after={
                "full_name": subscriber.full_name,
                "plate_number": subscriber.plate_number,
            },
        )
        return subscriber

    async def update_subscriber(
        self, subscriber_id: int, data: SubscriberUpdate, admin_id: int
    ) -> Subscriber:
        """Updates subscriber name, phone, and notes (plate_number is immutable)."""
        subscriber = await self.subscriber_repo.get_by_id(subscriber_id)
        if subscriber is None:
            raise SubscriberNotFoundError("Subscriber not found")

        before_state = {
            "full_name": subscriber.full_name,
            "phone_number": subscriber.phone_number,
            "notes": subscriber.notes,
        }

        updates: dict = {}
        if data.full_name is not None:
            updates["full_name"] = data.full_name
        if data.phone_number is not None:
            updates["phone_number"] = data.phone_number
        if data.notes is not None:
            updates["notes"] = data.notes

        if updates:
            await self.subscriber_repo.update_fields(subscriber, **updates)
            await self.db.commit()
            await self.db.refresh(subscriber)

        after_state = {
            "full_name": subscriber.full_name,
            "phone_number": subscriber.phone_number,
            "notes": subscriber.notes,
        }

        await self.audit_service.log(
            actor_id=admin_id,
            action="SUBSCRIBER_UPDATED",
            entity_type="subscriber",
            entity_id=subscriber.id,
            before=before_state,
            after=after_state,
        )
        return subscriber

    async def get_filtered(
        self,
        search: str | None,
        status_filter: str | None,
        plan_id: int | None,
        expiring_days: int | None,
        subscription_repo: SubscriptionRepository,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Subscriber], int]:
        """Returns paginated subscribers with attached active subscriptions and post-filters."""
        subscribers, total_count = await self.subscriber_repo.get_filtered(
            search=search,
            plan_id=plan_id,
            page=page,
            size=size,
        )

        # Attach active subscription for each subscriber in current page
        enriched_list = []
        today = cairo_now().date()
        for subscriber in subscribers:
            active_sub = await subscription_repo.get_active_for_subscriber(subscriber.id)
            subscriber.active_subscription = active_sub  # type: ignore[attr-defined]

            # Filter by status if provided
            if status_filter:
                filter_lower = status_filter.lower()
                if filter_lower == "active" and (not active_sub or active_sub.status.value != "ACTIVE"):
                    continue
                elif filter_lower == "expired" and (active_sub and active_sub.status.value == "ACTIVE"):
                    continue
                elif filter_lower == "cancelled" and (not active_sub or active_sub.status.value != "CANCELLED"):
                    continue

            # Filter by expiring soon if provided
            if expiring_days is not None and active_sub is not None:
                threshold = today + timedelta(days=expiring_days)
                if active_sub.end_date > threshold or active_sub.status.value != "ACTIVE":
                    continue

            enriched_list.append(subscriber)

        return enriched_list, total_count


__all__ = ["SubscriberService"]
