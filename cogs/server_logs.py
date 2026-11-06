import time
import discord
from discord.ext import commands

# ID канала для логов действий (создание/изменение/удаление каналов)
ACTION_LOG_CHANNEL_ID = 1566973996761612368

# Цвета для Embed
COLOR_CREATE = 0x2ECC71  # Зеленый
COLOR_DELETE = 0xE74C3C  # Красный
COLOR_UPDATE = 0xEC4899  # Розово-фиолетовый стиль под ваши логи


class ServerLogsCog(commands.Cog):
    """Логирование создания, изменения и удаления каналов."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        channel = guild.get_channel(ACTION_LOG_CHANNEL_ID) or self.bot.get_channel(ACTION_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ACTION_LOG_CHANNEL_ID)
            except discord.HTTPException:
                return None
        return channel  # type: ignore

    # 1. Канал создан
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        log_channel = await self._get_log_channel(channel.guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="📂 Канал создан",
            color=COLOR_CREATE,
        )
        embed.add_field(
            name="Канал",
            value=f"{channel.mention} (`{channel.id}`)",
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

    # 2. Канал удален
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        log_channel = await self._get_log_channel(channel.guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="🗑️ Канал удалён",
            color=COLOR_DELETE,
        )
        embed.add_field(
            name="Канал",
            value=f"#{channel.name} (`{channel.id}`)",
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

    # 3. Канал изменён (название, лимиты, тема)
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return

        changes = []
        
        # Изменение названия (вынесено на две разные строчки со стрелочкой)
        if before.name != after.name:
            changes.append(
                f"**Название изменено:**\n"
                f"▫️ Было: `#{before.name}`\n"
                f"▫️ Стало: {after.mention}"
            )

        # Изменения для голосовых каналов (лимиты и битрейт)
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            if before.user_limit != after.user_limit:
                old_limit = before.user_limit if before.user_limit else "0"
                new_limit = after.user_limit if after.user_limit else "0"
                changes.append(f"Лимит пользователей: **{old_limit}** ➔ **{new_limit}**")

            if before.bitrate != after.bitrate:
                changes.append(f"Битрейт изменён: **{before.bitrate // 1000} kbps** ➔ **{after.bitrate // 1000} kbps**")

        # Изменения для текстовых каналов (тема канала)
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            old_topic_str = before.topic.strip() if before.topic else ""
            new_topic_str = after.topic.strip() if after.topic else ""
            
            if old_topic_str != new_topic_str:
                display_old = old_topic_str if old_topic_str else "Пусто"
                display_new = new_topic_str if new_topic_str else "Пусто"
                changes.append(f"Тема изменена:\n**До:** {display_old}\n**После:** {display_new}")

        if not changes:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="✏️ Обновление канала",
            color=COLOR_UPDATE,
        )
        embed.add_field(
            name="Канал",
            value=f"{after.mention} (`{after.id}`)",
            inline=False,
        )
        
        for change in changes:
            embed.add_field(
                name="Изменение",
                value=change,
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
    await bot.add_cog(ServerLogsCog(bot))