import httpx
import logging
from app.core.config import settings


async def get_graph_token() -> str:
    url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        response.raise_for_status()
        return response.json().get("access_token")


async def create_outlook_event(user_email: str, start_time_str: str, end_time_str: str) -> bool:
    if not settings.MICROSOFT_CLIENT_ID:
        logging.warning(f"Ключі відсутні. Пропуск Outlook для {user_email} на {start_time_str}")
        return False

    try:
        token = await get_graph_token()
        event_data = {
            "subject": "📅 Чергування",
            "body": {
                "contentType": "HTML",
                "content": "Ви призначені на чергування. Будь ласка, будьте на зв'язку."
            },
            "start": {"dateTime": start_time_str, "timeZone": "Europe/Kyiv"},
            "end": {"dateTime": end_time_str, "timeZone": "Europe/Kyiv"}
        }

        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=event_data)
            response.raise_for_status()
            return True

    except Exception as e:
        logging.error(f"Помилка синхронізації: {str(e)}")
        return False