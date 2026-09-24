import pytest
from datetime import datetime
from types import SimpleNamespace
from utils.csv_export import (
    CSV_BOM,
    _piastres_to_egp_str,
    generate_sessions_csv,
    generate_shifts_csv,
)


def test_piastres_to_egp_str() -> None:
    assert _piastres_to_egp_str(None) == ""
    assert _piastres_to_egp_str(0) == "0.00"
    assert _piastres_to_egp_str(2550) == "25.50"
    assert _piastres_to_egp_str(100) == "1.00"


@pytest.mark.asyncio
async def test_csv_starts_with_bom() -> None:
    session = SimpleNamespace(
        id=1,
        card_code="CARD001",
        plate_number="123 أ ب ج",
        gate_number=1,
        operator_id=10,
        entry_time=datetime(2024, 8, 15, 10, 0),
        exit_time=datetime(2024, 8, 15, 12, 0),
        duration_minutes=120,
        status="COMPLETED",
        amount_charged=2500,
        is_lost_card=False,
        payment_method="CASH",
    )

    async def async_iter():
        yield session

    chunks = []
    async for chunk in generate_sessions_csv(async_iter(), {10: "علي"}):
        chunks.append(chunk)

    assert len(chunks) == 3  # BOM, header, 1 data row
    assert chunks[0] == CSV_BOM


@pytest.mark.asyncio
async def test_csv_header_row_is_arabic() -> None:
    async def async_empty():
        if False:
            yield None

    chunks = []
    async for chunk in generate_sessions_csv(async_empty(), {}):
        chunks.append(chunk)

    assert len(chunks) == 2  # BOM, header
    assert "رقم الجلسة" in chunks[1]
    assert "طريقة الدفع" in chunks[1]


@pytest.mark.asyncio
async def test_none_values_render_as_empty_string() -> None:
    session = SimpleNamespace(
        id=2,
        card_code="CARD002",
        plate_number=None,
        gate_number=2,
        operator_id=None,
        entry_time=datetime(2024, 8, 15, 10, 0),
        exit_time=None,
        duration_minutes=None,
        status="ACTIVE",
        amount_charged=None,
        is_lost_card=False,
        payment_method=None,
    )

    async def async_iter():
        yield session

    chunks = []
    async for chunk in generate_sessions_csv(async_iter(), {}):
        chunks.append(chunk)

    data_row = chunks[2]
    assert "None" not in data_row
    assert "null" not in data_row


@pytest.mark.asyncio
async def test_generate_shifts_csv() -> None:
    shift = SimpleNamespace(
        id=5,
        operator_id=3,
        gate_number=1,
        started_at=datetime(2024, 8, 15, 8, 0),
        ended_at=datetime(2024, 8, 15, 16, 0),
        closing_cash_egp=5000,
        session_count=12,
    )

    async def async_shifts():
        yield shift

    chunks = []
    async for chunk in generate_shifts_csv(async_shifts(), {3: "محمد"}, {5: 4800}):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0] == CSV_BOM
    assert "رقم الشيفت" in chunks[1]
    assert "الفرق (جنيه)" in chunks[1]
    # Data row: 50.00 closing, 48.00 computed, 2.00 diff
    assert "50.00" in chunks[2]
    assert "48.00" in chunks[2]
    assert "2.00" in chunks[2]
