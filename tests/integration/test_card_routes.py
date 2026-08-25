import pytest
from models.user import User, UserRole
from models.parking_card import ParkingCard, CardStatus

async def setup_admin(db_session, auth_service, async_client):
    hashed = auth_service.hash_password("adminpass")
    user = User(
        full_name="Admin User",
        username="admin1",
        hashed_password=hashed,
        role=UserRole.ADMIN,
        gate_number=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = auth_service.create_access_token(user.id, user.role.value)
    async_client.cookies.set("pgms_token", token)
    return user

@pytest.mark.asyncio
async def test_create_card_as_admin(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    response = await async_client.post(
        "/api/v1/cards/",
        json={"card_code": "CARD-TEST-001"}
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["card_code"] == "CARD-TEST-001"
    assert json_data["data"]["status"] == "available"

@pytest.mark.asyncio
async def test_create_card_duplicate(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    # First create
    await async_client.post("/api/v1/cards/", json={"card_code": "CARD-TEST-001"})
    # Second create duplicate
    response = await async_client.post("/api/v1/cards/", json={"card_code": "CARD-TEST-001"})
    assert response.status_code == 409
    assert response.json()["code"] == "CARD_CODE_ALREADY_EXISTS"

@pytest.mark.asyncio
async def test_create_card_invalid_barcode(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    response = await async_client.post("/api/v1/cards/", json={"card_code": "كرت-001"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_BARCODE_FORMAT"

@pytest.mark.asyncio
async def test_bulk_create_cards(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    response = await async_client.post(
        "/api/v1/cards/bulk",
        json={"card_codes": ["CARD-B1", "CARD-B2", "CARD-B3", "CARD-B4", "CARD-B5"]}
    )
    assert response.status_code == 201
    assert response.json()["data"]["created"] == 5

@pytest.mark.asyncio
async def test_bulk_create_conflict(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    # Pre-create card-b1
    await async_client.post("/api/v1/cards/", json={"card_code": "CARD-B1"})
    
    response = await async_client.post(
        "/api/v1/cards/bulk",
        json={"card_codes": ["CARD-B1", "CARD-B2"]}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BULK_CARD_CONFLICT"

@pytest.mark.asyncio
async def test_get_card_by_code(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    await async_client.post("/api/v1/cards/", json={"card_code": "CARD-TEST-001"})
    
    response = await async_client.get("/api/v1/cards/CARD-TEST-001")
    assert response.status_code == 200
    assert response.json()["data"]["card_code"] == "CARD-TEST-001"
    assert response.json()["data"]["status"] == "available"

@pytest.mark.asyncio
async def test_get_card_normalizes_code(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    await async_client.post("/api/v1/cards/", json={"card_code": "CARD-001"})
    
    response = await async_client.get("/api/v1/cards/card-001")
    assert response.status_code == 200
    assert response.json()["data"]["card_code"] == "CARD-001"

@pytest.mark.asyncio
async def test_update_card_status(async_client, db_session, auth_service):
    await setup_admin(db_session, auth_service, async_client)
    await async_client.post("/api/v1/cards/", json={"card_code": "CARD-TEST-001"})
    
    response = await async_client.patch(
        "/api/v1/cards/CARD-TEST-001/status",
        json={"status": "damaged"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "damaged"
