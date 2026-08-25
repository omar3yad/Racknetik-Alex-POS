from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from dependencies import require_operator
from models.user import User
from models.pricing_rule import PricingRule
from models.parking_card import ParkingCard, CardStatus
from models.parking_session import ParkingSession, SessionStatus
from repositories.session_repo import ParkingSessionRepository
from repositories.rate_repo import PricingRuleRepository
from services.session_service import SessionService
from services.card_service import CardService
from services.pricing_service import PricingService
from services.shift_service import ShiftService
from services.audit_service import AuditService
from services.plate_service import PlateService
from services.pricing_helpers import format_duration, format_egp
from schemas.receipt import ReceiptData
from utils.templates import load_translations
from services.exceptions import (
    CardNotFoundError,
    CardNotAvailableError,
    CardAlreadyActiveError,
    CardHasNoActiveSessionError,
    InvalidBarcodeFormatError,
    SessionNotFoundError,
    SessionNotActiveError,
    NoActiveShiftError,
    NoPricingRuleError,
)

router = APIRouter(prefix="/ui/operator", tags=["ui-operator"])

# Load translations for routing rendering errors
translations = load_translations()

def get_error_translation_key(e: Exception) -> str:
    mapping = {
        "CardNotFoundError": "errors.card_not_found",
        "CardAlreadyActiveError": "errors.card_already_active",
        "CardNotAvailableError": "errors.card_not_available",
        "NoActiveShiftError": "errors.no_active_shift",
        "InvalidBarcodeFormatError": "errors.invalid_barcode_format",
        "SessionNotFoundError": "errors.session_not_found",
        "SessionNotActiveError": "errors.no_active_session",
        "NoPricingRuleError": "errors.no_pricing_rule",
    }
    return mapping.get(e.__class__.__name__, "errors.server_error")

def get_session_repo(db: AsyncSession = Depends(get_db)) -> ParkingSessionRepository:
    return ParkingSessionRepository(db)

def get_pricing_repo(db: AsyncSession = Depends(get_db)) -> PricingRuleRepository:
    return PricingRuleRepository(db)

def get_pricing_service(db: AsyncSession = Depends(get_db)) -> PricingService:
    return PricingService(db)

def get_shift_service(db: AsyncSession = Depends(get_db)) -> ShiftService:
    audit_service = AuditService(db)
    return ShiftService(db, audit_service)

def get_session_service(db: AsyncSession = Depends(get_db)) -> SessionService:
    card_service = CardService(db)
    session_repo = ParkingSessionRepository(db)
    pricing_service = PricingService(db)
    audit_service = AuditService(db)
    shift_service = ShiftService(db, audit_service)
    plate_service = PlateService()
    return SessionService(
        db=db,
        card_service=card_service,
        session_repo=session_repo,
        pricing_service=pricing_service,
        shift_service=shift_service,
        audit_service=audit_service,
        plate_service=plate_service,
    )

@router.get("/shift/start")
async def start_shift_page(
    request: Request,
    current_user: User = Depends(require_operator),
    shift_service: ShiftService = Depends(get_shift_service),
):
    active = await shift_service.get_active_shift(current_user.id)
    if active:
        return RedirectResponse("/ui/operator/dashboard", status_code=303)
    
    settings = get_settings()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/shift_start.html",
        {"request": request, "user": current_user}
    )

@router.post("/shift/start")
async def open_shift(
    request: Request,
    opening_cash_egp: int = Form(...),
    current_user: User = Depends(require_operator),
    shift_service: ShiftService = Depends(get_shift_service),
):
    # Form value comes in EGP, convert to piastres internally
    opening_cash_piastres = opening_cash_egp * 100
    try:
        await shift_service.open_shift(
            operator_id=current_user.id,
            gate_number=current_user.gate_number,
            opening_cash_egp=opening_cash_piastres,
        )
    except ShiftAlreadyOpenError:
        pass
    return RedirectResponse("/ui/operator/dashboard", status_code=303)

@router.get("/shift/end")
async def end_shift_page(
    request: Request,
    current_user: User = Depends(require_operator),
    shift_service: ShiftService = Depends(get_shift_service),
):
    try:
        shift = await shift_service.require_active_shift(current_user.id)
    except NoActiveShiftError:
        return RedirectResponse("/ui/operator/dashboard", status_code=303)

    summary = await shift_service._compute_summary(shift, None)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/shift_end.html",
        {"request": request, "user": current_user, "shift": shift, "summary": summary}
    )

@router.post("/shift/end")
async def close_shift(
    request: Request,
    closing_cash_egp: int = Form(...),
    current_user: User = Depends(require_operator),
    shift_service: ShiftService = Depends(get_shift_service),
):
    try:
        shift = await shift_service.require_active_shift(current_user.id)
    except NoActiveShiftError:
        return RedirectResponse("/ui/operator/dashboard", status_code=303)

    closing_cash_piastres = closing_cash_egp * 100
    await shift_service.close_shift(
        shift_id=shift.id,
        operator_id=current_user.id,
        closing_cash_piastres=closing_cash_piastres,
    )

    # Clear cookie and redirect to login
    response = RedirectResponse("/ui/login", status_code=303)
    response.delete_cookie("pgms_token")
    return response

@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    current_user: User = Depends(require_operator),
    shift_service: ShiftService = Depends(get_shift_service),
    session_repo: ParkingSessionRepository = Depends(get_session_repo),
    pricing_repo: PricingRuleRepository = Depends(get_pricing_repo),
):
    shift = await shift_service.get_active_shift(current_user.id)
    sessions, total = [], 0
    if shift:
        sessions, total = await session_repo.get_by_shift(shift.id, page=1, size=10)
    
    active_rule = await pricing_repo.get_active()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/dashboard.html",
        {
            "request": request,
            "user": current_user,
            "shift": shift,
            "sessions": sessions,
            "session_total": total,
            "active_rule": active_rule,
        }
    )

@router.get("/entry")
async def entry_scan_page(
    request: Request,
    current_user: User = Depends(require_operator),
):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/entry.html",
        {"request": request, "user": current_user, "error": None}
    )

@router.post("/entry")
async def process_entry(
    request: Request,
    card_code: str = Form(...),
    plate_number: str = Form(""),
    current_user: User = Depends(require_operator),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session = await session_service.open_session(
            card_code=card_code,
            operator_id=current_user.id,
            plate_number=plate_number or None,
        )
    except Exception as e:
        key = get_error_translation_key(e)
        err_msg = translations.get(key, getattr(e, "message", "Internal server error"))
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "operator/entry.html",
            {"request": request, "user": current_user, "error": err_msg}
        )

    return RedirectResponse(f"/ui/operator/entry/confirm/{session.id}", status_code=303)

@router.get("/entry/confirm/{session_id}")
async def entry_confirm_page(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_operator),
    session_repo: ParkingSessionRepository = Depends(get_session_repo),
):
    session = await session_repo.get_by_id(session_id)
    if not session:
        return RedirectResponse("/ui/operator/dashboard", status_code=303)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/entry_confirm.html",
        {"request": request, "session": session}
    )

@router.get("/exit")
async def exit_scan_page(
    request: Request,
    error: str | None = None,
    current_user: User = Depends(require_operator),
):
    err_msg = None
    if error == "SESSION_NOT_ACTIVE":
        err_msg = translations.get("errors.no_active_session", "Session is not active")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/exit_scan.html",
        {"request": request, "user": current_user, "error": err_msg}
    )

@router.post("/exit/lookup")
async def exit_lookup(
    request: Request,
    card_code: str = Form(...),
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
    session_repo: ParkingSessionRepository = Depends(get_session_repo),
    pricing_service: PricingService = Depends(get_pricing_service),
):
    card_service = CardService(db)
    try:
        session = await card_service.validate_for_exit(card_code, session_repo)
        rule = await pricing_service.get_active_rule()
        calc = pricing_service.calculate(session, rule, datetime.utcnow())
    except Exception as e:
        key = get_error_translation_key(e)
        err_msg = translations.get(key, getattr(e, "message", "Internal server error"))
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "operator/exit_scan.html",
            {"request": request, "user": current_user, "error": err_msg}
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/exit_confirm.html",
        {"request": request, "session": session, "calc": calc, "rule": rule}
    )

@router.post("/exit/{session_id}/confirm")
async def exit_confirm_session(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_operator),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        session, calc = await session_service.close_session(session_id, current_user.id)
    except SessionNotActiveError:
        return RedirectResponse("/ui/operator/exit?error=SESSION_NOT_ACTIVE", status_code=303)
    except NoPricingRuleError as e:
        err_msg = translations.get("errors.no_pricing_rule", e.message)
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "operator/exit_scan.html",
            {"request": request, "user": current_user, "error": err_msg}
        )
    except Exception as e:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "operator/exit_scan.html",
            {"request": request, "user": current_user, "error": getattr(e, "message", str(e))}
        )

    return RedirectResponse(f"/ui/operator/receipt/{session.id}", status_code=303)

@router.get("/lost-card")
async def lost_card_page(
    request: Request,
    current_user: User = Depends(require_operator),
):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/lost_card.html",
        {"request": request, "user": current_user, "error": None, "sessions": None}
    )

@router.post("/lost-card")
async def process_lost_card_lookup(
    request: Request,
    plate_number: str = Form(...),
    notes: str = Form(""),
    current_user: User = Depends(require_operator),
    session_service: SessionService = Depends(get_session_service),
):
    sessions = await session_service.find_active_by_plate(plate_number)
    templates = request.app.state.templates
    if not sessions:
        err_msg = translations.get("errors.no_active_session_for_plate", "No active sessions found for this plate")
        return templates.TemplateResponse(
            "operator/lost_card.html",
            {"request": request, "user": current_user, "error": err_msg, "sessions": None}
        )
    elif len(sessions) == 1:
        return RedirectResponse(f"/ui/operator/lost-card/confirm/{sessions[0].id}", status_code=303)
    
    return templates.TemplateResponse(
        "operator/lost_card.html",
        {"request": request, "user": current_user, "error": None, "sessions": sessions, "notes": notes}
    )

@router.get("/lost-card/confirm/{session_id}")
async def lost_card_confirm_page(
    request: Request,
    session_id: int,
    notes: str | None = None,
    current_user: User = Depends(require_operator),
    session_repo: ParkingSessionRepository = Depends(get_session_repo),
    pricing_service: PricingService = Depends(get_pricing_service),
):
    session = await session_repo.get_by_id(session_id)
    if not session:
        return RedirectResponse("/ui/operator/lost-card", status_code=303)

    rule = await pricing_service.get_active_rule()
    calc = pricing_service.calculate_lost_card(session, rule, datetime.utcnow())

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "operator/lost_card_confirm.html",
        {"request": request, "session": session, "calc": calc, "rule": rule, "notes": notes}
    )

@router.post("/lost-card/confirm/{session_id}")
async def resolve_lost_card_confirm(
    session_id: int,
    notes: str = Form(""),
    current_user: User = Depends(require_operator),
    session_service: SessionService = Depends(get_session_service),
):
    await session_service.resolve_lost_card(
        session_id=session_id,
        operator_id=current_user.id,
        notes=notes or None,
    )
    return RedirectResponse(f"/ui/operator/receipt/{session_id}", status_code=303)

@router.get("/receipt/{session_id}")
async def print_receipt_page(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
    session_repo: ParkingSessionRepository = Depends(get_session_repo),
    session_service: SessionService = Depends(get_session_service),
):
    session = await session_repo.get_by_id(session_id)
    if not session:
        return RedirectResponse("/ui/operator/dashboard", status_code=303)

    # Fetch Operator Username
    operator_name = "Unknown"
    if session.exit_operator_id is not None:
        operator_res = await db.execute(
            select(User.username).where(User.id == session.exit_operator_id).limit(1)
        )
        operator_name = operator_res.scalar() or "Unknown"

    # Fetch Pricing Rule details
    rule_label = "Standard"
    rate_per_hour = 0
    grace_period_mins = 0
    lost_card_penalty = 0
    if session.pricing_rule_id is not None:
        rule_res = await db.execute(
            select(PricingRule).where(PricingRule.id == session.pricing_rule_id).limit(1)
        )
        rule = rule_res.scalars().first()
        if rule:
            rule_label = rule.label
            rate_per_hour = rule.rate_per_hour
            grace_period_mins = rule.grace_period_mins
            lost_card_penalty = rule.lost_card_penalty

    # Record receipt print timestamp
    await session_service.mark_receipt_printed(session_id)

    # Calculate receipt base/penalty details
    if session.is_lost_card:
        penalty_amount = lost_card_penalty
        base_amount = (session.amount_charged or 0) - lost_card_penalty
        is_grace_period = False
    else:
        penalty_amount = 0
        base_amount = session.amount_charged or 0
        is_grace_period = (session.duration_minutes or 0) <= grace_period_mins

    settings = get_settings()

    receipt_data = ReceiptData(
        session_id=session.id,
        card_code=session.card_code,
        plate_number=session.plate_number,
        gate_number=session.gate_number,
        operator_name=operator_name,
        entry_time=session.entry_time,
        exit_time=session.exit_time or datetime.utcnow(),
        duration_minutes=session.duration_minutes or 0,
        duration_display=format_duration(session.duration_minutes or 0),
        pricing_rule_label=rule_label,
        rate_per_hour=rate_per_hour,
        grace_period_mins=grace_period_mins,
        base_amount=base_amount,
        penalty_amount=penalty_amount,
        total_amount=session.amount_charged or 0,
        total_display=format_egp(session.amount_charged or 0),
        payment_method="نقدي",
        is_lost_card=session.is_lost_card,
        is_grace_period=is_grace_period,
        garage_name="جراج ركنتك",
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "receipts/thermal.html",
        {
            "request": request,
            "receipt": receipt_data,
            "garage_name": settings.APP_NAME,
        }
    )
