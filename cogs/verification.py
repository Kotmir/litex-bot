"""Верификация: автовыдача роли, /accept, /denied и оценка саппорта в ЛС."""
import logging
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import format_age, now_ts, staff_only, stars, today_str

log = logging.getLogger("litex.verification")

COMMENT_MAX = 400
REASON_MAX = 500

# ID роли практиканта (имеет доступ к /accept)
INTERN_ROLE_ID = 1566325500157366333

# ID канала для отправки логов верификации
VERIFICATION_LOG_CHANNEL_ID = 1567259462199148644


def can_accept():
    """Проверка прав для /accept: доступ у стаффа, администраторов и роли практиканта."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False

        user_role_ids = {role.id for role in interaction.user.roles}

        # Разрешаем, если есть роль практиканта или права администратора
        if INTERN_ROLE_ID in user_role_ids or interaction.user.guild_permissions.administrator:
            return True

        # Проверяем стандартные роли стаффа из config.py (на случай разных названий переменных)
        staff_role_ids: set[int] = set()
        for attr in ("STAFF_ROLE_IDS", "STAFF_ROLES", "MODERATOR_ROLE_IDS", "SUPPORT_ROLE_IDS"):
            val = getattr(config, attr, None)
            if isinstance(val, (list, tuple, set)):
                staff_role_ids.update(val)
        for attr in ("STAFF_ROLE_ID", "SUPPORT_ROLE_ID", "MODERATOR_ROLE_ID", "ADMIN_ROLE_ID"):
            val = getattr(config, attr, None)
            if isinstance(val, int):
                staff_role_ids.add(val)

        if user_role_ids & staff_role_ids:
            return True

        await interaction.response.send_message(
            "⛔ У вас нет прав для использования этой команды.", ephemeral=True
        )
        return False

    return app_commands.check(predicate)


# ═════════════════════════ Оценка саппорта в ЛС ═════════════════════════
def finished_view(chosen: int | None = None) -> discord.ui.View:
    """Неактивные кнопки после того, как отзыв оставлен."""
    view = discord.ui.View(timeout=None)
    for value in range(1, 6):
        view.add_item(
            discord.ui.Button(
                label=f"{value} ⭐",
                style=discord.ButtonStyle.success if value == chosen else discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"litex:done:{value}",
            )
        )
    return view


class ReviewModal(discord.ui.Modal):
    """Окно с необязательным комментарием к оценке."""

    comment = discord.ui.TextInput(
        label="Комментарий / Отзыв",
        style=discord.TextStyle.paragraph,
        placeholder="Необязательно — можно оставить только оценку",
        required=False,
        max_length=COMMENT_MAX,
    )

    def __init__(self, verification_id: int, rating: int, message: discord.Message | None) -> None:
        super().__init__(title=f"Оценка работы саппорта: {rating} ⭐", timeout=600)
        self.verification_id = verification_id
        self.rating = rating
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        db = interaction.client.db
        verification = await db.get_verification(self.verification_id)
        if verification is None or verification["user_id"] != interaction.user.id:
            await interaction.response.send_message("⛔ Эта оценка вам недоступна.", ephemeral=True)
            return

        comment = (self.comment.value or "").strip() or None
        review_id = await db.add_review(
            verification_id=self.verification_id,
            support_id=verification["support_id"],
            author_id=interaction.user.id,
            rating=self.rating,
            comment=comment,
            date=today_str(),
            created_at=now_ts(),
        )

        if review_id is None:
            await interaction.response.send_message(
                "✅ Вы уже оставили отзыв по этой проверке.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"💛 Спасибо за оценку! Вы поставили {stars(self.rating)}.", ephemeral=True
            )

        # Деактивируем кнопки под исходным сообщением в ЛС
        if self.message is not None:
            try:
                await self.message.edit(view=finished_view(self.rating if review_id else None))
            except discord.HTTPException:
                log.warning("Не удалось отключить кнопки оценки (verification #%s)", self.verification_id)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.exception("Ошибка при сохранении отзыва", exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Не удалось сохранить отзыв. Попробуйте позже.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Не удалось сохранить отзыв. Попробуйте позже.", ephemeral=True)
        except discord.HTTPException:
            pass


class RateButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"litex:rate:(?P<vid>[0-9]+):(?P<stars>[1-5])",
):
    """Кнопка «N ⭐». Работает и после перезапуска бота (custom_id хранит ID проверки)."""

    def __init__(self, verification_id: int, rating: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=f"{rating} ⭐",
                style=discord.ButtonStyle.secondary,
                custom_id=f"litex:rate:{verification_id}:{rating}",
            )
        )
        self.verification_id = verification_id
        self.rating = rating

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /
    ) -> "RateButton":
        return cls(int(match["vid"]), int(match["stars"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        db = interaction.client.db
        verification = await db.get_verification(self.verification_id)
        if verification is None or verification["user_id"] != interaction.user.id:
            await interaction.response.send_message("⛔ Эта оценка вам недоступна.", ephemeral=True)
            return
        if await db.review_exists(self.verification_id):
            await interaction.response.send_message(
                "✅ Вы уже оставили отзыв по этой проверке.", ephemeral=True
            )
            try:
                if interaction.message is not None:
                    await interaction.message.edit(view=finished_view())
            except discord.HTTPException:
                pass
            return
        await interaction.response.send_modal(
            ReviewModal(self.verification_id, self.rating, interaction.message)
        )


def rating_view(verification_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for value in range(1, 6):
        view.add_item(RateButton(verification_id, value))
    return view


# ═════════════════════════════════ Cog ═════════════════════════════════
class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._swept = False  # проход по участникам без ролей уже выполнен

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(RateButton)

    async def cog_unload(self) -> None:
        self.bot.remove_dynamic_items(RateButton)

    # ───────────────────── автовыдача стартовой роли ─────────────────────
    def _is_target_guild(self, guild: discord.Guild) -> bool:
        return not config.GUILD_ID or guild.id == config.GUILD_ID

    @staticmethod
    def _has_no_roles(member: discord.Member) -> bool:
        """True, если у участника нет ни одной роли (кроме @everyone)."""
        return not member.bot and len(member.roles) <= 1

    async def _give_start_role(self, member: discord.Member, reason: str) -> bool:
        role = member.guild.get_role(config.START_ROLE_ID)
        if role is None:
            log.warning("Стартовая роль %s не найдена на сервере %s", config.START_ROLE_ID, member.guild.id)
            return False
        try:
            await member.add_roles(role, reason=reason)
            return True
        except discord.HTTPException:
            log.exception("Не удалось выдать стартовую роль участнику %s", member.id)
            return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Новый участник → стартовая роль."""
        if member.bot or not self._is_target_guild(member.guild):
            return
        await self._give_start_role(member, "litex: стартовая роль при входе")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """При запуске бота выдаёт стартовую роль всем, у кого нет ролей (один раз за запуск)."""
        if self._swept:
            return
        self._swept = True
        for guild in self.bot.guilds:
            if self._is_target_guild(guild):
                await self._sweep_guild(guild)

    async def _sweep_guild(self, guild: discord.Guild) -> None:
        if not guild.chunked:
            await guild.chunk()
        targets = [m for m in guild.members if self._has_no_roles(m)]
        given = 0
        for member in targets:
            if await self._give_start_role(member, "litex: у участника не было ролей"):
                given += 1
        log.info("Сервер %s: участников без ролей — %d, стартовая роль выдана — %d", guild.id, len(targets), given)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Если у участника пропали все роли — возвращаем стартовую."""
        if not self._is_target_guild(after.guild):
            return
        if self._has_no_roles(after) and not self._has_no_roles(before):
            await self._give_start_role(after, "litex: у участника не осталось ролей")

    # ───────────────────────────── /accept ─────────────────────────────
    @app_commands.command(name="accept", description="Принять пользователя: верификация пройдена")
    @app_commands.describe(member="Пользователь, которого нужно принять")
    @app_commands.rename(member="пользователь")
    @app_commands.guild_only()
    @can_accept()
    async def accept(self, interaction: discord.Interaction, member: discord.Member) -> None:
        problem = self._precheck(interaction, member)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        support = interaction.user

        member_role = guild.get_role(config.MEMBER_ROLE_ID)
        start_role = guild.get_role(config.START_ROLE_ID)
        denied_role = guild.get_role(config.DENIED_ROLE_ID)
        if member_role is None:
            await interaction.followup.send("❌ Роль «Участник» не найдена на сервере — проверьте config.py.", ephemeral=True)
            return
        if member_role in member.roles:
            await interaction.followup.send(f"ℹ️ {member.mention} уже верифицирован.", ephemeral=True)
            return

        # Если человека ранее отклоняли — снимаем и роль отказа
        to_remove = [r for r in (start_role, denied_role) if r is not None and r in member.roles]
        error = await self._change_roles(
            member, add=[member_role], remove=to_remove, reason=f"litex: /accept от {support}"
        )
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        ts = now_ts()
        verification_id = await self.bot.db.add_verification(support.id, member.id, "accept", None, ts)

        embed = discord.Embed(
            title="✅ Верификация пройдена",
            color=config.COLOR_GREEN,
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
        )
        embed.add_field(name="🛡️ Проверил", value=f"{support.mention} (`{support}`)", inline=True)
        embed.add_field(name="👤 Принят", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🕒 Время", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Проверка #{verification_id}")

        await self._finish(interaction, member, support, verification_id, embed, accepted=True)

    # ───────────────────────────── /denied ─────────────────────────────
    @app_commands.command(name="denied", description="Отказать пользователю в верификации")
    @app_commands.describe(member="Пользователь, которому отказывают", reason="Причина отказа")
    @app_commands.rename(member="пользователь", reason="причина")
    @app_commands.guild_only()
    @staff_only()
    async def denied(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: app_commands.Range[str, 1, REASON_MAX],
    ) -> None:
        problem = self._precheck(interaction, member)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        support = interaction.user
        reason = reason.strip()

        denied_role = guild.get_role(config.DENIED_ROLE_ID)
        start_role = guild.get_role(config.START_ROLE_ID)
        if denied_role is None:
            await interaction.followup.send("❌ Роль отказа не найдена на сервере — проверьте config.py.", ephemeral=True)
            return

        to_remove = [start_role] if start_role is not None and start_role in member.roles else []
        error = await self._change_roles(
            member, add=[denied_role], remove=to_remove, reason=f"litex: /denied от {support}"
        )
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        ts = now_ts()
        verification_id = await self.bot.db.add_verification(support.id, member.id, "denied", reason, ts)

        created = member.created_at
        age = format_age(datetime.now(timezone.utc) - created)
        embed = discord.Embed(
            title="⛔ Отказ в верификации",
            color=config.COLOR_RED,
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
        )
        embed.add_field(name="🛡️ Проверил", value=f"{support.mention} (`{support}`)", inline=True)
        embed.add_field(name="👤 Кому отказано", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(
            name="📅 Возраст аккаунта",
            value=f"Создан: <t:{int(created.timestamp())}:D>\nПрошло: {age}" + ("" if age.startswith("меньше") else " назад"),
            inline=False,
        )
        embed.add_field(name="📄 Причина", value=reason[:1024], inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Проверка #{verification_id}")

        await self._finish(interaction, member, support, verification_id, embed, accepted=False)

    # ───────────────────────────── helpers ─────────────────────────────
    @staticmethod
    def _precheck(interaction: discord.Interaction, member: discord.Member) -> str | None:
        if member.bot:
            return "🤖 Ботов проверять не нужно."
        if member.id == interaction.user.id:
            return "⛔ Нельзя проверять самого себя."
        return None

    @staticmethod
    async def _change_roles(
        member: discord.Member,
        add: list[discord.Role],
        remove: list[discord.Role],
        reason: str,
    ) -> str | None:
        """Меняет роли. Возвращает текст ошибки или None, если всё прошло."""
        try:
            await member.add_roles(*add, reason=reason)
            if remove:
                await member.remove_roles(*remove, reason=reason)
        except discord.Forbidden:
            return (
                "⛔ У бота не хватает прав на выдачу ролей. Проверьте право «Управлять ролями» "
                "и что роль бота стоит **выше** выдаваемых ролей."
            )
        except discord.HTTPException:
            log.exception("Не удалось изменить роли участника %s", member.id)
            return "❌ Не удалось изменить роли пользователя. Попробуйте ещё раз."
        return None

    async def _finish(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        support: discord.abc.User,
        verification_id: int,
        embed: discord.Embed,
        accepted: bool,
    ) -> None:
        """Лог в канал + запрос оценки в ЛС + ответ саппорту."""
        warnings: list[str] = []

        if not await self._send_log(interaction.guild, embed):
            warnings.append("⚠️ Не удалось отправить запись в канал логов.")
        if not await self._send_rating_request(member, support, verification_id, accepted):
            warnings.append("⚠️ ЛС пользователя закрыты — запрос оценки не отправлен.")

        text = f"✅ {member.mention} принят(а)." if accepted else f"⛔ {member.mention} — отказ оформлен."
        if warnings:
            text += "\n" + "\n".join(warnings)
        await interaction.followup.send(text, ephemeral=True)

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> bool:
        channel = guild.get_channel(VERIFICATION_LOG_CHANNEL_ID)
        try:
            if channel is None:
                channel = await self.bot.fetch_channel(VERIFICATION_LOG_CHANNEL_ID)
            await channel.send(embed=embed)
            return True
        except (discord.HTTPException, AttributeError):
            log.exception("Не удалось отправить лог в канал %s", VERIFICATION_LOG_CHANNEL_ID)
            return False

    async def _send_rating_request(
        self,
        member: discord.Member,
        support: discord.abc.User,
        verification_id: int,
        accepted: bool,
    ) -> bool:
        result = "✅ Верификация пройдена" if accepted else "⛔ В верификации отказано"
        embed = discord.Embed(
            title="📝 Оцените работу саппорта",
            description=(
                f"{result}.\n\n"
                f"Пожалуйста, оцените работу саппорта <@{support.id}> (**{support.display_name}**), "
                f"который проводил вашу проверку.\n"
                f"Выберите оценку от 1 до 5 — после этого можно оставить комментарий (необязательно)."
            ),
            color=config.COLOR_GOLD,
        )
        try:
            await member.send(embed=embed, view=rating_view(verification_id))
            return True
        except discord.Forbidden:
            return False
        except discord.HTTPException:
            log.exception("Не удалось отправить ЛС пользователю %s", member.id)
            return False


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))