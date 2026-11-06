"""
Бот сидит в голосовом канале (ID: 1566992670004613201).

• При запуске заходит в канал (с паузой, чтобы Discord успел забыть прошлую сессию).
• Если бот вылетел из войса, он возвращается сам. После 3 вылетов за 30 минут 
  бот делает паузу на час.
• !join — зайти к тебе в канал, !leave — выйти (автовозврат выключается).
"""
import asyncio
import logging
import time
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

try:
    import nacl  # noqa: F401  (нужен для работы с голосовыми каналами в discord.py)
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

NACL_HINT = "Для голосовых каналов нужна библиотека PyNaCl: python -m pip install PyNaCl"

TARGET_CHANNEL_ID = 1566992670004613201  # ID целевого канала
AUTO_JOIN = True          # заходить в TARGET_CHANNEL_ID при запуске
STARTUP_DELAY = 15        # пауза перед первым заходом, сек
CONNECT_TIMEOUT = 30      # сколько ждать подключения
REJOIN_DELAY = 10         # пауза перед возвратом, если выгнали
MAX_FAILS = 3             # после стольких неудач подряд бот перестаёт пытаться
FAIL_WINDOW = 30 * 60     # ...в течение 30 минут
RETRY_AFTER_GIVE_UP = 60 * 60   # через сколько попробовать снова после «сдался»


class Voice(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._lock = asyncio.Lock()
        self._manual_leave = False
        self._fails: list = []
        self._gave_up = False
        self._task: Optional[asyncio.Task] = None
        if not HAS_NACL:
            print(f"⚠️ {NACL_HINT}", flush=True)
        elif AUTO_JOIN:
            self._task = bot.loop.create_task(self._startup())

    def cog_unload(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    # ───────────────────── Подключение ─────────────────────

    def _target(self) -> Optional[discord.VoiceChannel]:
        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        return channel if isinstance(channel, discord.VoiceChannel) else None

    def _register_fail(self) -> None:
        now = time.monotonic()
        self._fails = [t for t in self._fails if now - t < FAIL_WINDOW] + [now]
        if len(self._fails) >= MAX_FAILS and not self._gave_up:
            self._gave_up = True
            print(
                f"⚠️ Войс не держится ({MAX_FAILS} вылета за 30 мин) — делаю паузу на час. "
                "Голос Discord, скорее всего, режется сетью/VPN. Вернуть сразу: !join",
                flush=True,
            )
            self.bot.loop.create_task(self._retry_later())

    async def _retry_later(self) -> None:
        await asyncio.sleep(RETRY_AFTER_GIVE_UP)
        if self._manual_leave or not self._gave_up:
            return
        self._gave_up = False
        self._fails.clear()
        channel = self._target()
        if channel and channel.guild.voice_client is None and await self._connect(channel):
            print(f"🔁 Бот вернулся в голосовой канал:  {channel.name}", flush=True)

    async def _connect(self, channel: discord.VoiceChannel) -> bool:
        """Подключает или перемещает бота. True — успешно."""
        async with self._lock:
            vc = channel.guild.voice_client
            try:
                if vc and vc.is_connected():
                    if vc.channel.id != channel.id:
                        await vc.move_to(channel)
                    return True
                if vc:  # «зависшее» подключение
                    await vc.disconnect(force=True)
                await channel.connect(timeout=CONNECT_TIMEOUT, reconnect=False)
                return True
            except (asyncio.TimeoutError, discord.ClientException, discord.HTTPException, OSError) as e:
                logger.info("Не удалось подключиться к войсу: %s", e or type(e).__name__)
                self._register_fail()
                vc = channel.guild.voice_client
                if vc and not vc.is_connected():
                    try:
                        await vc.disconnect(force=True)
                    except Exception:
                        pass
                return False

    async def _startup(self) -> None:
        await self.bot.wait_until_ready()
        await asyncio.sleep(STARTUP_DELAY)
        channel = self._target()
        if channel is None:
            print(f"⚠️ Голосовой канал {TARGET_CHANNEL_ID} не найден.", flush=True)
            return
        if await self._connect(channel):
            print(f"🎤 Бот зашёл в голосовой канал:  {channel.name}", flush=True)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Если бота выгнали из канала (а не просто оборвалась связь) — возвращаемся."""
        if not HAS_NACL or not AUTO_JOIN or member.id != self.bot.user.id:
            return
        if self._manual_leave or self._gave_up:
            return
        if before.channel is None or after.channel is not None or before.channel.id != TARGET_CHANNEL_ID:
            return

        self._register_fail()
        if self._gave_up:
            return
        await asyncio.sleep(REJOIN_DELAY)
        vc = member.guild.voice_client
        if vc is not None or self._manual_leave or self._gave_up:
            return
        channel = self._target()
        if channel and await self._connect(channel):
            print(f"🔁 Бот вернулся в голосовой канал:  {channel.name}", flush=True)

    # ───────────────────── Команды ─────────────────────

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def join(self, ctx: commands.Context) -> None:
        """Подключает бота к твоему голосовому каналу."""
        if not HAS_NACL:
            await ctx.send(f"⚠️ {NACL_HINT}")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ Сначала сам зайди в голосовой канал!")
            return
        channel = ctx.author.voice.channel
        self._manual_leave = False
        self._gave_up = False
        self._fails.clear()
        msg = await ctx.send("⏳ Подключаюсь к голосовому каналу...")
        if await self._connect(channel):
            await msg.edit(content=f"🎤 Я в канале **{channel.name}**")
            print(f"🎤 Бот подключился по команде !join в канал: {channel.name}", flush=True)
        else:
            await msg.edit(content="⚠️ Не удалось подключиться. Похоже, голос Discord блокируется сетью — нужен VPN.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leave(self, ctx: commands.Context) -> None:
        """Отключает бота от голосового канала."""
        self._manual_leave = True
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await ctx.send("🔌 Отключился. Автовозврат выключен до `!join` или перезапуска.")
            print("🔌 Бот отключен от войса по команде !leave", flush=True)
        else:
            await ctx.send("⚠️ Меня сейчас нет в войсе.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voice(bot))