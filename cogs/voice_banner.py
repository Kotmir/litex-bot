"""
voice_banner.py — cog, который рисует баннер сервера со счётчиком людей в голосовых каналах.

Требования:
    pip install -U "discord.py>=2.0" "Pillow>=9.1"

    * Серверу должен быть доступен баннер (фича BANNER — буст-уровень 2+).
    * У бота есть право «Управление сервером» (Manage Guild).
    * Включены интенты: guilds, members, voice_states
      (без members бот не увидит часть участников в `channel.members`).

Подключение:
    await bot.load_extension("cogs.voice_banner")   # путь поправь под свою структуру

Как обновляется баннер:
    * Вход/выход из войса -> через EVENT_DEBOUNCE_SECONDS секунд баннер перерисовывается
      (серия событий подряд склеивается в одно обновление).
    * Между двумя правками баннера на одном сервере проходит не меньше MIN_EDIT_INTERVAL_SECONDS —
      это защита от rate limit Discord. Если изменение пришло раньше, оно применяется,
      как только кулдаун закончится.
    * Страховочная таска каждые CHECK_INTERVAL_SECONDS сверяет число с баннером, так что
      пропущенное событие или неудачная попытка не оставят на баннере устаревшее число.
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
from pathlib import Path

import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ — всё, что нужно подкручивать, лежит здесь
# ═══════════════════════════════════════════════════════════════════════════

# ── Файлы (пути относительно папки, из которой запускается бот) ────────────
BACKGROUND_PATH = Path("assets/banner_bg.png")
ICON_PATH = Path("assets/mic_icon.png")
FONT_PATH = Path("assets/minecraft.ttf")

# ── Поведение ──────────────────────────────────────────────────────────────
TARGET_GUILD_IDS: set[int] = set()   # пусто = все сервера, где доступен баннер
COUNT_BOTS = False                   # считать ли ботов в войсах
INCLUDE_STAGE_CHANNELS = False       # считать ли трибуны (Stage) вместе с войсами

# ── Частота обновления ─────────────────────────────────────────────────────
# Discord не публикует точный лимит на смену баннера. Если в логах появятся
# предупреждения о rate limit — просто увеличь MIN_EDIT_INTERVAL_SECONDS.
EVENT_DEBOUNCE_SECONDS = 3           # пауза после события, чтобы склеить серию входов/выходов
MIN_EDIT_INTERVAL_SECONDS = 20       # минимум между двумя правками баннера на одном сервере
CHECK_INTERVAL_SECONDS = 30          # страховочная сверка числа с баннером
RETRY_BACKOFF_SECONDS = 30          # пауза перед повтором после ошибки
EDIT_TIMEOUT_SECONDS = 45            # сколько ждать ответа Discord (при rate limit запрос «зависает»)

# ── Баннер ─────────────────────────────────────────────────────────────────
BANNER_SIZE = (960, 540)             # фон будет обрезан/масштабирован до этого размера

# ═══ Виджет. Все размеры сняты с примера (баннер 700×394) и пересчитаны на 960×540 ═══
# Раскладка внутри плашки, слева направо:  [отступ] [иконка] ........ [число] ........

# ── Плашка ─────────────────────────────────────────────────────────────────
PLATE_POSITION = (103, 203)          # левый верхний угол плашки (x, y)
PLATE_MIN_WIDTH = 333                # ширина для коротких чисел; длинные число расширяют плашку вправо
PLATE_HEIGHT = 160
PLATE_PADDING_RIGHT = 40             # минимальный отступ от числа до правого края плашки
PLATE_RADIUS = 18                    # скругление углов
PLATE_COLOR = (0, 0, 0, 150)        # RGBA: тёмная полупрозрачная заливка (последнее число — непрозрачность 0..255)
PLATE_OUTLINE_COLOR = None           # RGBA или None (без обводки)
PLATE_OUTLINE_WIDTH = 2

# ── Иконка микрофона ───────────────────────────────────────────────────────
ICON_SIZE = (69, 85)                 # иконка вписывается в этот прямоугольник (ширина, высота)
ICON_RESAMPLE = Image.Resampling.LANCZOS   # для пиксель-арта поставь Image.Resampling.NEAREST
ICON_LEFT = 36                       # отступ иконки от левого края плашки
ICON_OFFSET = (0, 2)                 # подгонка (dx, dy); по вертикали иконка и так центрируется

# ── Число ──────────────────────────────────────────────────────────────────
DIGIT_HEIGHT = 68                    # высота цифр в пикселях — размер шрифта подбирается сам
FONT_SIZE: int | None = None         # или задай размер шрифта вручную (тогда DIGIT_HEIGHT игнорируется)
TEXT_LEFT = 180                      # отступ левого края числа от левого края плашки
TEXT_OFFSET = (0, 2)                 # подгонка (dx, dy); по вертикали цифры и так центрируются
TEXT_COLOR = (235, 235, 235, 255)
TEXT_SHADOW_COLOR = (63, 63, 63, 255)
TEXT_SHADOW_OFFSET = (0, 0)          # (0, 0) — без тени (как в примере); (3, 3) — тень в стиле Minecraft

# ── Мягкое свечение вокруг иконки и числа ──────────────────────────────────
GLOW_COLOR = (255, 255, 255)
GLOW_SPREAD = 7                      # на сколько пикселей «раздувается» контур
GLOW_BLUR = 7                        # размытие
ICON_GLOW_OPACITY = 65               # 0..255, 0 — выключить
TEXT_GLOW_OPACITY = 28               # 0..255, 0 — выключить


class VoiceBanner(commands.Cog):
    """Обновляет баннер сервера в зависимости от числа людей в голосовых каналах."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # Ресурсы загружаются один раз в cog_load, а не при каждой отрисовке.
        self._background: Image.Image
        self._icon: Image.Image
        self._font: ImageFont.FreeTypeFont

        # guild_id -> число, которое сейчас отображено на баннере
        self._last_count: dict[int, int] = {}
        # guild_id -> время (time.monotonic), раньше которого баннер трогать нельзя
        self._next_edit_at: dict[int, float] = {}
        # по одному замку на сервер: событие и страховочная таска не должны править баннер одновременно
        self._locks: dict[int, asyncio.Lock] = {}
        # отложенные обновления, запущенные событиями
        self._pending: dict[int, asyncio.Task] = {}

    # ───────────────────────── жизненный цикл ─────────────────────────────

    async def cog_load(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_assets)
        self.update_banners.start()

    async def cog_unload(self) -> None:
        self.update_banners.cancel()
        for task in self._pending.values():
            task.cancel()
        self._pending.clear()

    def _load_assets(self) -> None:
        for path in (BACKGROUND_PATH, ICON_PATH, FONT_PATH):
            if not path.is_file():
                raise FileNotFoundError(f"VoiceBanner: не найден файл {path.resolve()}")

        background = Image.open(BACKGROUND_PATH).convert("RGBA")
        self._background = ImageOps.fit(background, BANNER_SIZE, Image.Resampling.LANCZOS)

        icon = Image.open(ICON_PATH).convert("RGBA")
        # Обрезаем прозрачные поля, чтобы ICON_SIZE описывал именно видимую часть иконки.
        visible = icon.getchannel("A").getbbox()
        if visible:
            icon = icon.crop(visible)
        self._icon = ImageOps.contain(icon, ICON_SIZE, ICON_RESAMPLE)

        self._font = self._load_font()

    @staticmethod
    def _ink_bbox(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int, int, int]:
        """Реальные границы нарисованного текста относительно точки (0, baseline).

        Считаем по пикселям, а не через font.getbbox(): у шрифтов есть боковые отступы
        глифов, и из-за них число «съезжало» бы относительно заданной позиции.
        """
        pad = 20
        width = int(font.getlength(text)) + pad * 2
        height = int(font.size) * 2
        baseline = height // 2
        canvas = Image.new("L", (width, height), 0)
        ImageDraw.Draw(canvas).text((pad, baseline), text, font=font, fill=255, anchor="ls")
        left, top, right, bottom = canvas.getbbox() or (pad, baseline, pad, baseline)
        return left - pad, top - baseline, right - pad, bottom - baseline

    @classmethod
    def _load_font(cls) -> ImageFont.FreeTypeFont:
        if FONT_SIZE is not None:
            return ImageFont.truetype(str(FONT_PATH), FONT_SIZE)

        # Подбираем размер так, чтобы цифры получились высотой DIGIT_HEIGHT пикселей —
        # у разных шрифтов одинаковый size даёт разную высоту цифр.
        probe_size = 100
        probe = ImageFont.truetype(str(FONT_PATH), probe_size)
        _, top, _, bottom = cls._ink_bbox(probe, "0123456789")
        size = max(1, round(probe_size * DIGIT_HEIGHT / (bottom - top)))
        return ImageFont.truetype(str(FONT_PATH), size)

    # ───────────────────────── подсчёт и отрисовка ────────────────────────

    def _is_target(self, guild: discord.Guild) -> bool:
        if TARGET_GUILD_IDS and guild.id not in TARGET_GUILD_IDS:
            return False
        return "BANNER" in guild.features

    @staticmethod
    def _count_voice_members(guild: discord.Guild) -> int:
        channels: list[discord.abc.Connectable] = list(guild.voice_channels)
        if INCLUDE_STAGE_CHANNELS:
            channels += guild.stage_channels
        return sum(
            1
            for channel in channels
            for member in channel.members
            if COUNT_BOTS or not member.bot
        )

    @staticmethod
    def _glow(mask: Image.Image, opacity: int) -> Image.Image:
        """Мягкое свечение по контуру маски (маска — картинка режима L)."""
        if GLOW_SPREAD > 0:
            mask = mask.filter(ImageFilter.MaxFilter(GLOW_SPREAD * 2 + 1))
        if GLOW_BLUR > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(GLOW_BLUR))
        layer = Image.new("RGBA", mask.size, (*GLOW_COLOR, 0))
        layer.putalpha(mask.point(lambda value: value * opacity // 255))
        return layer

    def _text_layer(
        self, size: tuple[int, int], xy: tuple[int, int], text: str, color: tuple[int, int, int, int]
    ) -> Image.Image:
        # Слой заранее залит цветом текста с нулевой альфой — иначе края букв получат тёмную кайму.
        layer = Image.new("RGBA", size, (*color[:3], 0))
        ImageDraw.Draw(layer).text(xy, text, font=self._font, fill=color, anchor="ls")
        return layer

    def _render_banner(self, count: int) -> bytes:
        """Синхронная отрисовка (вызывается в потоке, чтобы не блокировать event loop)."""
        text = str(count)
        icon_w, icon_h = self._icon.size

        # Границы «чернил» числа относительно базовой линии (anchor="ls"): top < 0 — над линией.
        ink_left, ink_top, ink_right, ink_bottom = self._ink_bbox(self._font, text)

        plate_w = max(PLATE_MIN_WIDTH, TEXT_LEFT + (ink_right - ink_left) + PLATE_PADDING_RIGHT)
        plate_h = PLATE_HEIGHT

        icon_x = ICON_LEFT + ICON_OFFSET[0]
        icon_y = (plate_h - icon_h) // 2 + ICON_OFFSET[1]
        # Левый край числа — ровно в TEXT_LEFT, а цифры по вертикали центрируются в плашке.
        text_x = TEXT_LEFT - ink_left + TEXT_OFFSET[0]
        baseline_y = round(plate_h / 2 - (ink_top + ink_bottom) / 2) + TEXT_OFFSET[1]

        # Весь виджет собирается на отдельном слое размером с плашку.
        widget = Image.new("RGBA", (plate_w, plate_h), (0, 0, 0, 0))
        ImageDraw.Draw(widget).rounded_rectangle(
            (0, 0, plate_w - 1, plate_h - 1),
            radius=PLATE_RADIUS,
            fill=PLATE_COLOR,
            outline=PLATE_OUTLINE_COLOR,
            width=PLATE_OUTLINE_WIDTH,
        )

        # Свечение — под иконкой и числом.
        if ICON_GLOW_OPACITY > 0:
            icon_mask = Image.new("L", widget.size, 0)
            icon_mask.paste(self._icon.getchannel("A"), (icon_x, icon_y))
            widget = Image.alpha_composite(widget, self._glow(icon_mask, ICON_GLOW_OPACITY))
        if TEXT_GLOW_OPACITY > 0:
            text_mask = Image.new("L", widget.size, 0)
            ImageDraw.Draw(text_mask).text(
                (text_x, baseline_y), text, font=self._font, fill=255, anchor="ls"
            )
            widget = Image.alpha_composite(widget, self._glow(text_mask, TEXT_GLOW_OPACITY))

        # Иконка и число.
        widget.alpha_composite(self._icon, dest=(icon_x, icon_y))
        if TEXT_SHADOW_OFFSET != (0, 0):
            shadow_xy = (text_x + TEXT_SHADOW_OFFSET[0], baseline_y + TEXT_SHADOW_OFFSET[1])
            widget.alpha_composite(self._text_layer(widget.size, shadow_xy, text, TEXT_SHADOW_COLOR))
        widget.alpha_composite(self._text_layer(widget.size, (text_x, baseline_y), text, TEXT_COLOR))

        banner = self._background.copy()
        banner.alpha_composite(widget, dest=PLATE_POSITION)

        buffer = io.BytesIO()
        banner.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    # ───────────────────────── обновление баннера ─────────────────────────

    async def _update_guild_banner(self, guild: discord.Guild, count: int) -> bool:
        """Генерирует и загружает баннер. Возвращает True при успехе."""
        loop = asyncio.get_running_loop()
        try:
            image_bytes = await loop.run_in_executor(None, self._render_banner, count)
        except Exception:
            log.exception("Не удалось отрисовать баннер для сервера %s (%s)", guild.name, guild.id)
            self._next_edit_at[guild.id] = time.monotonic() + RETRY_BACKOFF_SECONDS
            return False

        try:
            await asyncio.wait_for(
                guild.edit(banner=image_bytes, reason=f"Voice banner: {count} в голосовых"),
                timeout=EDIT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            log.warning(
                "Discord не ответил за %s с на обновление баннера %s (%s) — похоже на rate limit",
                EDIT_TIMEOUT_SECONDS, guild.name, guild.id,
            )
        except discord.Forbidden:
            log.error("Нет права «Управление сервером» на сервере %s (%s)", guild.name, guild.id)
        except discord.HTTPException as exc:
            log.warning(
                "Discord отклонил обновление баннера на %s (%s): %s", guild.name, guild.id, exc
            )
        else:
            self._last_count[guild.id] = count
            self._next_edit_at[guild.id] = time.monotonic() + MIN_EDIT_INTERVAL_SECONDS
            log.info("Баннер сервера %s обновлён: %d в голосовых", guild.name, count)
            return True

        self._next_edit_at[guild.id] = time.monotonic() + RETRY_BACKOFF_SECONDS
        return False

    async def _sync_guild(self, guild: discord.Guild) -> None:
        """Сверяет число людей с баннером и при необходимости обновляет его."""
        if not self._is_target(guild):
            return

        lock = self._locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            count = self._count_voice_members(guild)
            if count == self._last_count.get(guild.id):
                return  # на баннере уже актуальное число — лишний запрос не нужен
            if time.monotonic() < self._next_edit_at.get(guild.id, 0.0):
                return  # кулдаун: обновим позже (отложенной задачей или страховочной таской)
            await self._update_guild_banner(guild, count)

    async def _debounced_sync(self, guild: discord.Guild) -> None:
        """Ждёт, пока склеится серия событий и закончится кулдаун, затем обновляет баннер."""
        try:
            cooldown_left = self._next_edit_at.get(guild.id, 0.0) - time.monotonic()
            await asyncio.sleep(max(EVENT_DEBOUNCE_SECONDS, cooldown_left + 0.1))
            await self._sync_guild(guild)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка при отложенном обновлении баннера сервера %s", guild.id)

    # ───────────────────────── события и фоновая таска ────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Мут/дефен/стрим не меняют число людей — такие события пропускаем.
        if before.channel == after.channel:
            return
        if member.bot and not COUNT_BOTS:
            return

        guild = member.guild
        if not self._is_target(guild):
            return

        pending = self._pending.get(guild.id)
        if pending is not None and not pending.done():
            return  # обновление уже запланировано — оно учтёт и это событие
        self._pending[guild.id] = asyncio.create_task(self._debounced_sync(guild))

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def update_banners(self) -> None:
        # Страховка: сверяем все сервера, даже если событие потерялось или прошлая попытка не удалась.
        for guild in self.bot.guilds:
            try:
                await self._sync_guild(guild)
            except Exception:
                # Одна ошибка не должна убивать всю таску (tasks.loop останавливается на исключении).
                log.exception("Ошибка при обработке сервера %s", guild.id)

    @update_banners.before_loop
    async def _before_update_banners(self) -> None:
        await self.bot.wait_until_ready()

        for guild_id in TARGET_GUILD_IDS:
            guild = self.bot.get_guild(guild_id)
            if guild is not None and "BANNER" not in guild.features:
                log.warning(
                    "На сервере %s (%s) недоступен баннер (нужен буст-уровень 2+)",
                    guild.name, guild.id,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceBanner(bot))
