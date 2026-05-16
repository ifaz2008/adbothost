import httpx

from app.config import settings


class BackendClient:
    def __init__(self) -> None:
        self.base_url = settings.telegram_backend_url.rstrip("/")

    async def telegram_login(self, telegram_id: int, display_name: str | None) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/auth/telegram-login",
                json={"telegram_id": str(telegram_id), "display_name": display_name},
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_bots(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/bots", headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            return response.json()

    async def get_credits(self, token: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/credits/me", headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            return response.json()
