import httpx
import logging
from app.core.config import settings
from app.models.models import DayOffBalance

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

async def create_outlook_ooo_event(user_email: str, start_date: str, end_date: str) -> bool:
    """Створює подію Out of Office (Відпустка/Вихідний) на цілий день."""
    if not settings.MICROSOFT_CLIENT_ID:
        logging.warning(f"Ключі відсутні. Пропуск OOO для {user_email} з {start_date} по {end_date}")
        return False

    try:
        token = await get_graph_token()
        event_data = {
            "subject": "🌴 Out of Office",
            "body": {
                "contentType": "HTML",
                "content": "Я зараз у відпустці або на законному вихідному."
            },
            "isAllDay": True,
            "showAs": "oof",  # Статус Out of Office
            "start": {"dateTime": f"{start_date}T00:00:00", "timeZone": "Europe/Kyiv"},
            # Outlook вимагає, щоб кінець AllDay події був наступним днем опівночі
            "end": {"dateTime": f"{end_date}T23:59:59", "timeZone": "Europe/Kyiv"}
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
        logging.error(f"Помилка створення OOO: {str(e)}")
        return False




async def set_user_auto_reply(user_email: str, start_date: str, end_date: str, leave_type: str) -> bool:
    """Налаштовує автоматичну відповідь в Outlook (Automatic Replies)."""
    if not settings.MICROSOFT_CLIENT_ID:
        return False

    try:
        token = await get_graph_token()
        msg = "відпустці" if leave_type == "vacation" else "на лікарняному/відгулі"

        settings_data = {
            "automaticRepliesSetting": {
                "status": "scheduled",
                "externalAudience": "all",
                "internalReplyMessage": f"<html><body>Привіт! Я перебуваю у {msg} до {end_date} і не маю доступу до пошти.</body></html>",
                "externalReplyMessage": f"<html><body>Вітаю! Я буду поза офісом до {end_date}. З термінових питань звертайтесь до менеджера.</body></html>",
                "scheduledStartDateTime": {
                    "dateTime": f"{start_date}T00:00:00",
                    "timeZone": "Europe/Kyiv"
                },
                "scheduledEndDateTime": {
                    "dateTime": f"{end_date}T23:59:59",
                    "timeZone": "Europe/Kyiv"
                }
            }
        }


        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailboxSettings"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            # Використовуємо PATCH для оновлення налаштувань
            response = await client.patch(url, headers=headers, json=settings_data)
            response.raise_for_status()
            return True
    except Exception as e:
        logging.error(f"Помилка встановлення автовідповіді: {str(e)}")
        return False

