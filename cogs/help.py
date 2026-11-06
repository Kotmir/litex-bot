"""Команда /cheatsheet — шпаргалка по функционалу бота."""
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import is_staff


def build_cheatsheet() -> discord.Embed:
    gates = " ".join(f"<#{cid}>" for cid in sorted(config.GATE_VOICE_CHANNEL_IDS))

    embed = discord.Embed(
        title="📖 Шпаргалка по боту litex",
        description="Верификация новичков, аналитика саппортов и отзывы о их работе.",
        color=config.COLOR_BLURPLE,
    )
    embed.add_field(
        name="👤 Для всех участников",
        value=(
            "`/support_top` — рейтинг саппортов по числу проверок\n"
            "`/support_profile member` — профиль саппорта: статистика за сутки / неделю / месяц / "
            "всё время, время в проходной, средняя оценка\n"
            "`/cheatsheet` — эта шпаргалка"
        ),
        inline=False,
    )
    embed.add_field(
        name="🛡️ Для саппортов и администраторов",
        value=(
            f"`/accept пользователь` — принять: выдаёт <@&{config.MEMBER_ROLE_ID}> "
            f"и снимает <@&{config.START_ROLE_ID}>\n"
            f"`/denied пользователь причина` — отказать: выдаёт <@&{config.DENIED_ROLE_ID}>, "
            f"снимает <@&{config.START_ROLE_ID}>, причина уходит в лог\n"
            f"Каждая проверка записывается в статистику и попадает в <#{config.LOG_CHANNEL_ID}>."
        ),
        inline=False,
    )
    embed.add_field(
        name="⭐ Оценка саппорта",
        value=(
            "После `/accept` и `/denied` проверенному приходит ЛС с кнопками `1 ⭐` … `5 ⭐`. "
            "Клик открывает форму с необязательным комментарием. "
            "Один отзыв на одну проверку. Если ЛС закрыты — оценка не запрашивается."
        ),
        inline=False,
    )
    embed.add_field(
        name="📋 Отзывы",
        value=(
            "В профиле саппорта кнопка **«Просмотреть отзывы верификации»** — "
            f"по {config.REVIEWS_PER_PAGE} отзывов на странице, листать можно `◀` `▶`."
        ),
        inline=False,
    )
    embed.add_field(
        name="🤖 Работает автоматически",
        value=(
            f"• новичок при входе получает <@&{config.START_ROLE_ID}>; её же получают все, у кого нет ролей\n"
            f"• время саппортов в проходной ({gates}) считается само и показывается в профиле"
        ),
        inline=False,
    )
    embed.set_footer(text="litex • верификация и аналитика саппортов")
    return embed


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="cheatsheet", description="Шпаргалка по боту и его функциям")
    @app_commands.describe(public="Отправить в канал для всех (доступно только саппортам)")
    @app_commands.guild_only()
    async def cheatsheet(self, interaction: discord.Interaction, public: bool = False) -> None:
        can_publish = is_staff(interaction.user)
        ephemeral = not (public and can_publish)

        note = None
        if public and not can_publish:
            note = "ℹ️ Отправлять шпаргалку в канал могут только саппорты — показываю её только вам."
        await interaction.response.send_message(content=note, embed=build_cheatsheet(), ephemeral=ephemeral)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
