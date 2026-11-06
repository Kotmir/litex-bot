import time
import discord
from discord.ext import commands

# ID канала для логов голосовых каналов
VOICE_LOG_CHANNEL_ID = 1566964737038622831

# Розово-фиолетовый цвет полоски (0xEC4899 — розовый, 0xA855F7 — фиолетовый)
COLOR_VOICE_LOG = 0xEC4899


class VoiceLogsCog(commands.Cog):
    """Логирование входов, выходов и переходов в голосовых каналах."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        channel = guild.get_channel(VOICE_LOG_CHANNEL_ID) or self.bot.get_channel(VOICE_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(VOICE_LOG_CHANNEL_ID)
            except discord.HTTPException:
                return None
        return channel  # type: ignore

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Игнорируем ботов и изменения состояния микрофона/наушников внутри одного и того же канала
        if member.bot or before.channel == after.channel:
            return

        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            return

        now_ts = int(time.time())

        # 1. Зашёл в голосовой канал
        if before.channel is None and after.channel is not None:
            description = f"🟢 <t:{now_ts}:T> {member.mention} зашёл в **{after.channel.name}**"

        # 2. Вышел из голосового канала
        elif before.channel is not None and after.channel is None:
            description = f"🔴 <t:{now_ts}:T> {member.mention} вышел из **{before.channel.name}**"

        # 3. Перешёл из одного голосового канала в другой
        elif before.channel is not None and after.channel is not None:
            description = (
                f"🟣 <t:{now_ts}:T> {member.mention} перешёл из **{before.channel.name}** "
                f"в **{after.channel.name}**"
            )
        else:
            return

        embed = discord.Embed(
            title="🔊 Голосовые каналы",
            description=description,
            color=COLOR_VOICE_LOG,
        )

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceLogsCog(bot))