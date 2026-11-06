import time
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

# ID канала для логов модерации (📁・модерация)
MOD_LOG_CHANNEL_ID = 1566966732373885070

# (Опционально) ID канала-ловушки для спам-ботов (укажите ID канала или оставьте None)
HONEYPOT_CHANNEL_ID: int | None = None

# Розово-фиолетовая палитра (при желании можно поменять на классический красный 0xED4245 и зеленый 0x2ECC71)
COLOR_PINK = 0xEC4899    # Для банов, тайм-аутов и ловушки
COLOR_PURPLE = 0xA855F7  # Для разбанов и снятия тайм-аутов


class ModLogsCog(commands.Cog):
    """Логирование банов, разбанов, тайм-аутов и канала-ловушки."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        channel = guild.get_channel(MOD_LOG_CHANNEL_ID) or self.bot.get_channel(MOD_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MOD_LOG_CHANNEL_ID)
            except discord.HTTPException:
                return None
        return channel  # type: ignore

    # 1. Пользователь забанен
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member) -> None:
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="🔨 Пользователь забанен",
            description=(
                f"**{user.name}** (`{user.id}`)\n"
                f"🕓 **Время:** <t:{now_ts}:F> (<t:{now_ts}:R>)"
            ),
            color=COLOR_PINK,
        )

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # 2. Пользователь разбанен
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        embed = discord.Embed(
            title="🤝 Пользователь разбанен",
            description=(
                f"**{user.name}** (`{user.id}`)\n"
                f"🕓 **Время:** <t:{now_ts}:F> (<t:{now_ts}:R>)"
            ),
            color=COLOR_PURPLE,
        )

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # 3. Выдан или снят тайм-аут
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.timed_out_until == after.timed_out_until:
            return

        log_channel = await self._get_log_channel(after.guild)
        if not log_channel:
            return

        now = datetime.now(timezone.utc)
        now_ts = int(now.timestamp())

        # Если выдан новый тайм-аут
        if after.timed_out_until and after.timed_out_until > now:
            until_ts = int(after.timed_out_until.timestamp())
            embed = discord.Embed(
                title="⏱️ Выдан тайм-аут",
                description=(
                    f"Пользователь {after.mention} получил тайм-аут.\n"
                    f"🔒 **Истекает:** <t:{until_ts}:F> (<t:{until_ts}:R>)\n"
                    f"🕓 **Выдано:** <t:{now_ts}:F>"
                ),
                color=COLOR_PINK,
            )
            try:
                await log_channel.send(embed=embed)
            except discord.HTTPException:
                pass

        # Если тайм-аут был снят вручную досрочно
        elif before.timed_out_until and before.timed_out_until > now and after.timed_out_until is None:
            embed = discord.Embed(
                title="🔓 Тайм-аут снят",
                description=(
                    f"С пользователя {after.mention} снят тайм-аут.\n"
                    f"🕓 **Время:** <t:{now_ts}:F> (<t:{now_ts}:R>)"
                ),
                color=COLOR_PURPLE,
            )
            try:
                await log_channel.send(embed=embed)
            except discord.HTTPException:
                pass

    # 4. Канал-ловушка (если HONEYPOT_CHANNEL_ID задан)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not HONEYPOT_CHANNEL_ID or not message.guild or message.author.bot:
            return
        if message.channel.id != HONEYPOT_CHANNEL_ID:
            return
        if not isinstance(message.author, discord.Member):
            return
        # Не наказываем администраторов
        if message.author.guild_permissions.administrator:
            return

        member = message.author
        guild = message.guild

        # Выдаем тайм-аут на 28 дней
        try:
            await member.timeout(timedelta(days=28), reason="Сработал канал-ловушка")
        except discord.HTTPException:
            pass

        # Удаляем сообщения пользователя за последний час во всех текстовых каналах
        deleted_count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        for ch in guild.text_channels:
            try:
                deleted = await ch.purge(
                    limit=100,
                    after=cutoff,
                    check=lambda m: m.author.id == member.id,
                )
                deleted_count += len(deleted)
            except discord.HTTPException:
                continue

        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🍯 Сработал канал-ловушка",
            description=(
                f"**Кто:** {member.mention} (`{member.id}`)\n"
                f"**Тайм-аут:** выдан на 28 дней\n"
                f"**Удалено сообщений за час:** {deleted_count}"
            ),
            color=COLOR_PINK,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogsCog(bot))