# Parking Garage Management System — Constitution

> **Version:** 1.0  
> **Status:** Authoritative. All contributors must read and follow this document before writing any code.

---

## 1. Purpose

This document defines the non-negotiable rules, architectural decisions, and design constraints for the Parking Garage Management System (PGMS). It exists to keep the codebase consistent, maintainable, and deployable on constrained hardware from day one.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| API Framework | FastAPI (Python 3.11+) | Async-first; use `async def` for all route handlers |
| ORM | SQLAlchemy 2.x (async) | Use `AsyncSession`; no raw SQL except for reporting queries |
| Database | SQLite (dev) / PostgreSQL (prod) | Must be switchable via `DATABASE_URL` env var only |
| Templating | Jinja2 | Server-side rendering for operator UI pages |
| Styling | Tailwind CSS (CDN) or Bootstrap 5 | Tailwind preferred; no custom CSS frameworks |
| Validation | Pydantic v2 | All request/response bodies and config values |
| Task Queue | None (Phase 1) | Add Celery + Redis only if async jobs are required later |
| Auth | FastAPI built-in + JWT (python-jose) | No third-party auth services |

**No other frameworks or major libraries may be added without a team decision and an update to this document.**

---

## 3. Project Structure

Strict clean architecture. Every layer has one job and may only import inward.
```
pgms/
├── main.py # FastAPI app factory; mounts routers only
├── config.py # Settings via pydantic-settings; reads .env
├── database.py # Engine, AsyncSession factory, Base
│
├── models/ # SQLAlchemy ORM models (database shape)
│ ├── vehicle.py
│ ├── ticket.py
│ └── rate.py
│
├── schemas/ # Pydantic schemas (API contracts & validation)
│ ├── vehicle.py
│ ├── ticket.py
│ └── rate.py
│
├── routes/ # FastAPI routers (HTTP only — no business logic)
│ ├── tickets.py
│ ├── vehicles.py
│ ├── rates.py
│ └── reports.py
│
├── services/ # Business logic (pure Python, no HTTP concepts)
│ ├── ticket_service.py
│ ├── pricing_service.py
│ └── plate_service.py
│
├── repositories/ # Database access layer (CRUD wrappers)
│ ├── ticket_repo.py
│ └── vehicle_repo.py
│
├── templates/ # Jinja2 HTML templates
│ ├── base.html
│ ├── tickets/
│ └── reports/
│
├── static/ # CSS, minimal JS, receipt print styles
│ └── print.css
│
└── tests/
├── unit/
└── integration/
```
### Layer Rules

- **Routes** call **Services** only. Routes never touch `models/` or `repositories/` directly.
- **Services** call **Repositories** only. Services contain all business rules.
- **Repositories** call **SQLAlchemy** only. No business logic; no HTTP exceptions.
- **Models** are imported only by repositories and `database.py`.
- **Schemas** are imported by routes and services. Never by repositories.

Violating layer boundaries is a blocking code review issue.

---

## 4. Hardware Constraints — Sunmi V2 POS Terminal

The operator-facing UI **will run on a Sunmi V2** Android POS device (5.99" screen, ~360px viewport width). Every UI decision must respect these constraints.

### 4.1 UI / UX Rules

- **Mobile-first, always.** Design for 360–400px width. Desktop layout is a bonus, never the baseline.
- **No horizontal scrolling** on any operator screen, ever.
- **Touch targets** must be at minimum `48×48px`. Use large buttons for primary actions (check-in, check-out, print).
- **Minimal JavaScript.** Avoid heavy SPA frameworks. Use `<form>` POST submissions with Jinja2 templates. Vanilla JS only for receipt printing trigger and plate input formatting.
- **No external CDN calls at runtime.** Bundle or self-host Tailwind (use the CLI build) and any fonts. The terminal may have no internet access.
- **Page weight target:** each operator page must load under 150 KB total (HTML + CSS + JS).
- **No animations or transitions** that are not GPU-accelerated. The Sunmi V2 has limited CPU.

### 4.2 58mm Thermal Printer — Receipt Rules

- Receipts are triggered via the browser `window.print()` API against a dedicated print stylesheet (`/static/print.css`).
- **Print area width: 58mm (≈ 220px at 96dpi).** All receipt content must fit within this width without wrapping unintentionally.
- Use a **monospace font** (e.g., `Courier New`) for receipt content to ensure column alignment.
- All non-receipt UI must be `display: none` in `@media print`.
- Receipt templates live in `templates/receipts/`. They are separate Jinja2 templates, not embedded in page templates.
- **Required receipt fields:** ticket number, card barcode, plate number (optional, Arabic + Latin if entered), entry time, exit time, duration, amount charged, currency (EGP), operator ID, garage name.
- Font size on receipts: **minimum 10pt** for readability on thermal paper.
- No images or logos on receipts (thermal rendering is unreliable and slow).

---

## 5. Localization — Arabic (RTL) & Egyptian License Plates

Arabic support is a first-class requirement, not an afterthought.

### 5.1 Language & Direction

- All Jinja2 base templates must set `<html lang="ar" dir="rtl">` as the default.
- Use `dir="auto"` on individual input fields where mixed-direction input (Arabic/Latin) is expected.
- CSS logical properties (`margin-inline-start`, `padding-inline-end`) must be used instead of directional properties (`margin-left`, `padding-right`) everywhere in the stylesheet.
- All UI strings must be stored in a `translations/ar.json` file. No hardcoded Arabic strings in templates.

### 5.2 Egyptian License Plates

Egyptian plates mix Arabic letters and Hindu-Arabic numerals (e.g., **ن ي ش ١٥٩** or in data: `ن ي ش 159`).

- **Optional Field:** Recording the license plate is optional. Barcode scanning is the primary method for check-in and check-out.
- The canonical plate storage format in the database is: Arabic letters (space-separated) + space + Western numerals, stored as a single UTF-8 string. Example: `"ن ي ش 159"`.
- A dedicated `plate_service.py` must handle all normalization when a plate is provided:
  - Strip extra whitespace.
  - Convert Eastern Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) to Western (0–9) before storage.
  - Validate that the plate contains 1–3 Arabic letters and 1–4 digits.
  - Reject plates that do not conform; return a structured validation error.
- The plate input field in the UI must use `dir="rtl"` and `inputmode="text"`. A thin JS helper must reorder characters as the operator types so the display matches the physical plate layout.
- Plate search must be diacritic-insensitive (normalize with `unicodedata.normalize('NFKC', ...)` before comparison).
- Plates are displayed in receipts and screens using the stored canonical format, rendered RTL.

### 5.3 Currency & Numbers

- All monetary values are stored as **integer piastres** (1 EGP = 100 piastres) in the database. Never store floats for money.
- Display formatting (e.g., `٢٥٫٠٠ ج.م`) is handled by a Jinja2 custom filter `format_egp`. This filter must produce both Arabic-numeral and Western-numeral variants controlled by a config flag.
- Datetime display must use the **Egyptian locale** (`ar_EG`) for month names and weekdays when rendered in Arabic context.

---

## 6. API Design Rules

- All API endpoints are prefixed `/api/v1/`.
- Operator UI routes (HTML) are prefixed `/ui/`.
- Every endpoint must have a Pydantic response model. No returning raw ORM objects.
- HTTP status codes must be semantically correct (201 for creation, 404 for not found, 422 for validation errors — FastAPI default).
- All error responses follow this schema:
```json
  { "detail": "Human-readable message", "code": "MACHINE_READABLE_CODE" }
```
- Pagination is required on any list endpoint: `?page=1&size=20`. Default page size is 20; maximum is 100.

---

## 7. Database Rules

- Every model must have: `id` (integer PK), `created_at`, `updated_at` (auto-managed timestamps).
- No `CASCADE DELETE` on financial records (tickets, payments). Use soft deletes (`is_deleted: bool`).
- All migrations are managed by **Alembic**. Never modify the database schema manually or outside of a migration file.
- Migration files must include a meaningful `message` and must be reviewed before merging.
- Database connection string comes exclusively from `config.py` → environment variable `DATABASE_URL`. It must never appear hardcoded anywhere else.

---

## 8. Security Rules

- Never log sensitive data: plate numbers in full, payment amounts, or user credentials.
- All operator actions (check-in, check-out, rate change) must be associated with an `operator_id` and recorded in an immutable audit log table.
- JWT tokens expire in 8 hours. No refresh tokens in Phase 1.
- Input from the plate field must be sanitized before any database query.
- CORS must be explicitly configured; wildcard origins (`*`) are forbidden in production.

---

## 9. Testing Requirements

- **Unit tests** are required for all `services/` functions. Target: 90% coverage on the services layer.
- **Integration tests** are required for all API routes, using `httpx.AsyncClient` against a test SQLite database.
- No PR may be merged if it reduces overall test coverage below 80%.
- Tests live in `tests/unit/` and `tests/integration/` and mirror the source structure.
- Use `pytest` with `pytest-asyncio`. No `unittest` style.

---

## 10. Code Style & Quality

- Formatter: **Black** (line length 88). Non-negotiable.
- Linter: **Ruff**. All rules in `pyproject.toml`; no inline suppressions without a comment explaining why.
- Type hints are **mandatory** on all function signatures. Use `mypy` in CI.
- Docstrings are required on all service methods and repository methods. Google style.
- No `print()` statements in production code. Use Python `logging` with structured log levels.

---

## 11. Environment & Configuration

- All configuration is read from environment variables via `pydantic-settings` in `config.py`.
- A `.env.example` file must be kept up to date with every new config key.
- Three environments are recognized: `development`, `staging`, `production`. Behavior may differ (e.g., SQLite vs PostgreSQL, debug mode).
- `DEBUG=True` must never reach a production deployment. CI must enforce this.

---

## 12. Contribution Rules

1. Every feature or fix lives on its own branch: `feature/`, `fix/`, `chore/`.
2. PRs must reference an issue or ticket number.
3. PRs that touch `services/` or `models/` require two reviewers.
4. Any change to this `constitution.md` requires unanimous team approval.
5. "It works on my machine" is not an acceptable test. All tests must pass in CI before merge.

---

*This document is the law of the project. When in doubt, re-read it.*