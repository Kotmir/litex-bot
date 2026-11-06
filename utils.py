"""Вспомогательные функции: проверка прав, форматирование времени и т.п."""
from datetime import datetime, timedelta

import discord
from discord import app_commands

import config


def is_staff(member) -> bool:
    """True, если у участника есть роль саппорта/стаффа или право Administrator."""
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    return any(role.id in config.STAFF_ROLE_IDS for role in member.roles)


def staff_only():
    """Декоратор слэш-команд: доступ только для стаффа/администраторов."""

    async def predicate(interaction: discord.Interaction) -> bool:
        return is_staff(interaction.user)

    return app_commands.check(predicate)


def now_ts() -> int:
    return int(datetime.now().timestamp())


def today_str() -> str:
    """Текущая дата в формате ДД.ММ.ГГГГ (в часовом поясе из config)."""
    return datetime.now(config.TIMEZONE).strftime("%d.%m.%Y")


def stars(rating: int) -> str:
    return "⭐" * max(0, min(5, int(rating)))


def format_duration(seconds: int) -> str:
    """Секунды → «X ч Y мин»."""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    return f"{hours} ч {minutes} мин"


def format_age(delta: timedelta) -> str:
    """Возраст аккаунта словами: «1 г. 2 мес. 5 дн.»."""
    days = max(delta.days, 0)
    if days == 0:
        return "меньше суток"
    years, rest = divmod(days, 365)
    months, days = divmod(rest, 30)
    parts = []
    if years:
        parts.append(f"{years} г.")
    if months:
        parts.append(f"{months} мес.")
    if days:
        parts.append(f"{days} дн.")
    return " ".join(parts)
