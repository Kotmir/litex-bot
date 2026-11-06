"""Учёт времени саппортов в голосовых каналах «проходной»."""
import logging
import time

import discord
from discord.ext import commands, tasks

import config
from utils import is_staff

log = logging.getLogger("litex.voice")

FLUSH_MINUTES = 5  # как часто время из открытых сессий дописывается в БД


class VoiceTracker(commands.Cog):
    """Считает секунды, проведённые саппортами в каналах проходной.

    Перемещение между каналами проходной считается непрерывным присутствием.
    Открытые сессии каждые 5 минут сохраняются в БД, поэтому при падении
    бота теряется не больше этого промежутка.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.sessions: dict[int, float] = {}  # user_id -> время начала (unix)

    async def cog_load(self) -> None:
        self.flush_loop.start()

    async def cog_unload(self) -> None:
        self.flush_loop.cancel()
        # Сохраняем всё накопленное при остановке бота
        for user_id in list(self.sessions):
            await self._close_session(user_id)

    # ─────────────────────────── события ───────────────────────────
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Подхватываем тех, кто уже сидит в проходной после (пере)запуска."""
        present: set[int] = set()
        for channel_id in config.GATE_VOICE_CHANNEL_IDS:
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                present.update(m.id for m in channel.members if not m.bot and is_staff(m))

        for user_id in list(self.sessions):
            if user_id not in present:
                del self.sessions[user_id]
        now = time.time()
        for user_id in present:
            self.sessions.setdefault(user_id, now)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        if member.bot:
            return
        was_in = before.channel is not None and before.channel.id in config.GATE_VOICE_CHANNEL_IDS
        now_in = after.channel is not None and after.channel.id in config.GATE_VOICE_CHANNEL_IDS
        if was_in == now_in:
            return  # не входил/не выходил (мьют, стрим, переход между каналами проходной и т.п.)

        if now_in:
            if is_staff(member):
                self.sessions[member.id] = time.time()
        else:
            await self._close_session(member.id)

    # ───────────────────────── подсчёт времени ─────────────────────────
    async def _close_session(self, user_id: int) -> None:
        start = self.sessions.pop(user_id, None)
        if start is None:
            return
        seconds = int(time.time() - start)
        if seconds > 0:
            await self.bot.db.add_voice_time(user_id, seconds)

    @tasks.loop(minutes=FLUSH_MINUTES)
    async def flush_loop(self) -> None:
        now = time.time()
        for user_id, start in list(self.sessions.items()):
            seconds = int(now - start)
            if seconds <= 0 or user_id not in self.sessions:
                continue
            # Сначала сдвигаем начало (синхронно), потом пишем в БД —
            # так выход из канала во время записи не удвоит время.
            self.sessions[user_id] = start + seconds
            await self.bot.db.add_voice_time(user_id, seconds)

    @flush_loop.before_loop
    async def _before_flush(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceTracker(bot))
