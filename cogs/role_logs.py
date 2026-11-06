import time
import discord
from discord.ext import commands

# ID канала для логов изменения ролей
ROLE_LOG_CHANNEL_ID = 1566962265280876554

# Розовый цвет полоски
COLOR_ROLE_LOG = 0xEC4899


class RoleLogsCog(commands.Cog):
    """Логирование выдачи и снятия ролей у участников."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        channel = guild.get_channel(ROLE_LOG_CHANNEL_ID) or self.bot.get_channel(ROLE_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ROLE_LOG_CHANNEL_ID)
            except discord.HTTPException:
                return None
        return channel  # type: ignore

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        before_roles = set(before.roles)
        after_roles = set(after.roles)

        if before_roles == after_roles:
            return

        added_roles = after_roles - before_roles
        removed_roles = before_roles - after_roles

        if not added_roles and not removed_roles:
            return

        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="🏷️ Изменение ролей участника",
            color=COLOR_ROLE_LOG,
        )
        embed.add_field(
            name="Участник",
            value=f"{after.mention} (`{after.id}`)",
            inline=False,
        )

        if added_roles:
            added_text = ", ".join(role.mention for role in added_roles)
            embed.add_field(
                name="Выданы роли",
                value=added_text,
                inline=False,
            )

        if removed_roles:
            removed_text = ", ".join(role.mention for role in removed_roles)
            embed.add_field(
                name="Сняты роли",
                value=removed_text,
                inline=False,
            )

        embed.add_field(
            name="Время",
            value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)",
            inline=False,
        )

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RoleLogsCog(bot))