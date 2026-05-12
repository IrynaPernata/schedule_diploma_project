import pytest
from datetime import date
from pydantic import ValidationError

from app.core.security import get_password_hash, verify_password, create_access_token, decode_token
from app.schemas.schemas import LeaveCreate
from app.services.outlook import create_outlook_event
from app.core.config import settings


def test_security_password_hashing():
    """Тестування криптографічного модуля"""
    raw_password = "diploma_secure_password_2026"
    hashed = get_password_hash(raw_password)

    assert raw_password != hashed
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_lifecycle():
    """Перевірка генерації та розшифровки JWT-токена"""
    payload_data = {"sub": "12345678-1234-5678-1234-567812345678", "role": "manager"}

    token = create_access_token(payload_data)
    assert isinstance(token, str)
    assert len(token) > 20

    decoded_payload = decode_token(token)

    assert decoded_payload["sub"] == payload_data["sub"]
    assert decoded_payload["role"] == payload_data["role"]
    assert "exp" in decoded_payload  # Перевірка наявності часу "життя" токена


def test_pydantic_schema_validation():
    """Тестування DTO об'єктів та захисту від невалідних даних"""
    valid_data = {
        "date_from": date(2026, 5, 1),
        "date_to": date(2026, 5, 10),
        "type": "vacation"
    }
    leave = LeaveCreate(**valid_data)
    assert leave.type == "vacation"

    invalid_data = {
        "date_from": "not-a-date",
        "date_to": "not-a-date",
        "type": "vacation"
    }
    with pytest.raises(ValidationError):
        LeaveCreate(**invalid_data)


@pytest.mark.asyncio
async def test_outlook_service_graceful_degradation():
    """Перевірка стійкості (Fault Tolerance) при відсутності ключів Outlook"""
    original_client_id = settings.MICROSOFT_CLIENT_ID
    settings.MICROSOFT_CLIENT_ID = ""

    result = await create_outlook_event("test@company.com", "2026-05-01T09:00:00", "2026-05-01T18:00:00")

    assert result is False

    settings.MICROSOFT_CLIENT_ID = original_client_id