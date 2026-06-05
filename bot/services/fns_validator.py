import httpx
from bot.config import FNS_API_URL, FNS_API_KEY

async def verify_receipt_with_fns(date: str, amount: float, fp: str, number: str) -> bool:
    if not FNS_API_URL or not FNS_API_KEY:
        return True  # без ключа пропускаем
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(FNS_API_URL, json={"fp": fp, "sum": amount, "date": date, "number": number, "key": FNS_API_KEY})
            return resp.status_code == 200 and resp.json().get("found", False)
        except:
            return False