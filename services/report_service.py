from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from repositories.subscription_repo import SubscriptionRepository
from schemas.subscriptions import SubscriptionRevenueSummary, PlanRevenueResponse
from utils.time import CAIRO_TZ


class ReportService:
    def __init__(self, db=None):
        self.db = db
        pass

    async def get_subscription_revenue_summary(
        self,
        start_date: date | None,
        end_date: date | None,
        plan_id: int | None,
        subscription_repo: SubscriptionRepository,
    ) -> SubscriptionRevenueSummary:
        """Computes aggregated subscription financial metrics over a Cairo date range."""
        start_utc: datetime | None = None
        end_utc: datetime | None = None

        if start_date is not None:
            cairo_start = datetime.combine(start_date, time.min).replace(tzinfo=CAIRO_TZ)
            start_utc = cairo_start.astimezone(timezone.utc).replace(tzinfo=None)

        if end_date is not None:
            # Inclusive end date means up to midnight of next day
            cairo_end = datetime.combine(end_date, time.max).replace(tzinfo=CAIRO_TZ)
            end_utc = cairo_end.astimezone(timezone.utc).replace(tzinfo=None)

        rows = await subscription_repo.get_revenue_by_plan(start_utc, end_utc, plan_id)

        by_plan = [
            PlanRevenueResponse(
                plan_id=row["plan_id"],
                plan_label=row["plan_label"],
                subscription_count=row["subscription_count"],
                total_piastres=row["total_piastres"],
            )
            for row in rows
        ]

        total_subscriptions = sum(p.subscription_count for p in by_plan)
        total_revenue_piastres = sum(p.total_piastres for p in by_plan)
        avg_revenue_piastres = (
            total_revenue_piastres // max(total_subscriptions, 1) if total_subscriptions > 0 else 0
        )

        return SubscriptionRevenueSummary(
            total_subscriptions=total_subscriptions,
            total_revenue_piastres=total_revenue_piastres,
            avg_revenue_piastres=avg_revenue_piastres,
            by_plan=by_plan,
        )


__all__ = ["ReportService"]
