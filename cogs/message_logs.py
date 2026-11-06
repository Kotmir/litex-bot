import time
import discord
from discord.ext import commands

# ID канала для логов сообщений
MESSAGE_LOG_CHANNEL_ID = 1566960574279983194

# Розово-фиолетовая палитра
COLOR_PINK = 0xEC4899    # Насыщенный розовый (для удаленных сообщений)
COLOR_PURPLE = 0xA855F7  # Яркий фиолетовый (для измененных сообщений)


class MessageLogsCog(commands.Cog):
    """Логирование удаленных и измененных сообщений."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel = guild.get_channel(MESSAGE_LOG_CHANNEL_ID) or self.bot.get_channel(MESSAGE_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MESSAGE_LOG_CHANNEL_ID)
            except discord.HTTPException:
                return None
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        # Игнорируем ЛС, ботов и сам канал логов
        if not message.guild or message.author.bot or message.channel.id == MESSAGE_LOG_CHANNEL_ID:
            return

        log_channel = await self._get_log_channel(message.guild)
        if not log_channel:
            return

        # Формируем блок "Содержание" (текст + вложения со скрепкой 📎)
        content_parts = []
        if message.content:
            content_parts.append(message.content)

        if message.attachments:
            for att in message.attachments:
                content_parts.append(f"📎 [{att.filename}]({att.proxy_url})")

        if message.stickers:
            for sticker in message.stickers:
                content_parts.append(f"🏷️ Стикер: {sticker.name}")

        content_text = "\n".join(content_parts) if content_parts else "*Пустое сообщение / Embed*"
        if len(content_text) > 1024:
            content_text = content_text[:1021] + "..."

        now_ts = int(time.time())

        embed = discord.Embed(
            title="🗑️ Сообщение удалено",
            color=COLOR_PINK,
        )
        embed.add_field(
            name="Автор",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Канал",
            value=message.channel.mention,
            inline=False,
        )
        embed.add_field(
            name="Содержание",
            value=content_text,
            inline=False,
        )
        embed.add_field(
            name="Время",
            value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)",
            inline=False,
        )

        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                embed.set_image(url=att.proxy_url)
                break

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.channel.id == MESSAGE_LOG_CHANNEL_ID:
            return
        if before.content == after.content:
            return

        log_channel = await self._get_log_channel(before.guild)
        if not log_channel:
            return

        before_text = before.content or "*Пусто*"
        after_text = after.content or "*Пусто*"

        if len(before_text) > 1024:
            before_text = before_text[:1021] + "..."
        if len(after_text) > 1024:
            after_text = after_text[:1021] + "..."

        now_ts = int(time.time())

        embed = discord.Embed(
            title="✏️ Сообщение изменено",
            color=COLOR_PURPLE,
        )
        embed.add_field(
            name="Автор",
            value=f"{before.author.mention} (`{before.author.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Канал",
            value=f"{before.channel.mention} • [Перейти к сообщению]({after.jump_url})",
            inline=False,
        )
        embed.add_field(
            name="До изменения",
            value=before_text,
            inline=False,
        )
        embed.add_field(
            name="После изменения",
            value=after_text,
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
    await bot.add_cog(MessageLogsCog(bot))