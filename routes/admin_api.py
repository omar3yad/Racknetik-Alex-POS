from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import require_admin
from models.user import User
from repositories.subscription_repo import SubscriptionRepository
from services.subscription_service import SubscriptionService
from services.report_service import ReportService
from schemas.subscriptions import SubscriptionRevenueSummary, SubscriptionDashboardStats

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/reports/subscriptions")
async def get_subscription_reports(
    start_date: date | None = None,
    end_date: date | None = None,
    plan_id: int | None = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get subscription revenue breakdown by plan and totals."""
    subscription_repo = SubscriptionRepository(db)
    report_service = ReportService(db)
    summary = await report_service.get_subscription_revenue_summary(
        start_date=start_date,
        end_date=end_date,
        plan_id=plan_id,
        subscription_repo=subscription_repo,
    )
    return {"data": summary.model_dump(mode="json")}


@router.get("/stats/subscriptions")
async def get_subscription_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get subscription stats for admin dashboard."""
    subscription_repo = SubscriptionRepository(db)
    sub_service = SubscriptionService(
        db=db,
        subscription_repo=subscription_repo,
        plan_repo=None,
        card_service=None,
        audit_service=None,
    )
    stats = await sub_service.get_dashboard_stats()
    return {"data": stats.model_dump(mode="json")}
