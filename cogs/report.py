from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

# ID канала для отправки жалоб
REPORT_CHANNEL_ID = 1566980990847557704

# Розово-фиолетовый цвет полоски
COLOR_REPORT = 0xEC4899

# Месяцы на русском для футера
MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}


def get_custom_time_string() -> str:
    """Возвращает время в формате: 09.10.2026 21:08"""
    now = datetime.now(timezone.utc)
    day = f"{now.day:02d}"
    month = f"{now.month:02d}"
    year = now.year
    hour = f"{now.hour:02d}"
    minute = f"{now.minute:02d}"
    return f"{day}.{month}.{year} {hour}:{minute}"


class ReportCog(commands.Cog):
    """Система жалоб (/report) для сервера Litex."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_report_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel = guild.get_channel(REPORT_CHANNEL_ID) or self.bot.get_channel(REPORT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(REPORT_CHANNEL_ID)
            except discord.HTTPException:
                return None
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @app_commands.command(
        name="report",
        description="Подать жалобу на участника сервера"
    )
    @app_commands.describe(
        member="Пользователь, на которого подаётся жалоба.",
        reason="Причина жалобы.",
        proof="Скриншот-доказательство (необязательно)."
    )
    @app_commands.guild_only()
    async def report(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
        proof: discord.Attachment | None = None
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        # Защита от жалобы на самого себя или на бота
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Нельзя подать жалобу на самого себя.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ Нельзя подать жалобу на бота.", ephemeral=True)
            return

        log_channel = await self._get_report_channel(interaction.guild)
        if not log_channel:
            await interaction.response.send_message("❌ Канал для приема жалоб не настроен или недоступен боту.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Формируем Embed как на вашем скриншоте
        embed = discord.Embed(
            title="🚨 Новая жалоба",
            color=COLOR_REPORT,
        )
        
        # Поля автора и нарушителя
        embed.add_field(
            name="Автор жалобы",
            value=f"{interaction.user.mention}\n`{interaction.user.id}`",
            inline=True,
        )
        embed.add_field(
            name="На кого подана жалоба",
            value=f"{member.mention}\n`{member.id}`",
            inline=True,
        )
        
        # Причина
        embed.add_field(
            name="Причина",
            value=reason,
            inline=False,
        )

        # Миниатюра (аватарка сервера Litex справа вверху, как на скрине)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        # Если прикрепили файл-доказательство (картинку)
        if proof:
            if proof.content_type and proof.content_type.startswith("image/"):
                embed.set_image(url=proof.url)
            else:
                embed.add_field(name="Файл доказательства", value=f"[{proof.filename}]({proof.url})", inline=False)

        # Футер в точном стиле скриншота: "Сервер: Litex • Дата Время"
        time_str = get_custom_time_string()
        embed.set_footer(text=f"Сервер: {interaction.guild.name} • {time_str}")

        try:
            await log_channel.send(embed=embed)
            await interaction.followup.send("✅ Ваша жалоба успешно отправлена администрации!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Произошла ошибка при отправке жалобы: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReportCog(bot))