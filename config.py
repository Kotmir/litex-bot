"""Конфигурация бота litex.

Токен и технические параметры берутся из файла `.env`,
все ID ролей и каналов лежат ниже в виде констант.
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw.isdigit() else default


# ───────────────────────────── .env ─────────────────────────────
TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()
# ID сервера. Если задан — слэш-команды синхронизируются мгновенно только на нём.
# Если 0 — глобальная синхронизация (до часа ожидания) и бот работает на любых серверах.
GUILD_ID: int = _int_env("GUILD_ID")
DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "litex.db"))
# Часовой пояс для дат отзывов (ДД.ММ.ГГГГ)
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))

# ───────────────────────────── Роли ─────────────────────────────
START_ROLE_ID = 1559508180868796556    # стартовая роль (при входе)
MEMBER_ROLE_ID = 1535921559955574907   # успешная верификация (Участник)
DENIED_ROLE_ID = 1564804922577264751   # отказ (Недопущен)

# Роли саппортов / стаффа (+ любой с правом Administrator)
STAFF_ROLE_IDS = frozenset(
    {
        1535921559955574908,
        1535921559955574909,
        1564803540818591826,
        1535977357482135643,
    }
)

# ──────────────────────────── Каналы ────────────────────────────
LOG_CHANNEL_ID = 1564805779561783296   # логи принятий и отказов

# Голосовые каналы «проходной» (учёт времени саппортов)
GATE_VOICE_CHANNEL_IDS = frozenset(
    {
        1560782015681269811,
        1560782118479470672,
        1560782266857291877,
    }
)

# ─────────────────────────── Оформление ──────────────────────────
COLOR_GOLD = 0xF1C40F
COLOR_BLURPLE = 0x5865F2
COLOR_GREEN = 0x2ECC71
COLOR_RED = 0xE74C3C

REVIEWS_PER_PAGE = 5
