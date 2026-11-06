"""Топ активности, профиль саппорта и просмотр отзывов."""
import math
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import format_duration, is_staff, stars

DAY = 86400


# ═══════════════════════════ Отзывы (пагинация) ═══════════════════════════
def _quote(comment: str) -> str:
    """Комментарий → цитата курсивом: `> *текст*` (построчно, без разметки и пингов)."""
    lines = [ln.strip() for ln in comment.splitlines() if ln.strip()]
    safe = (discord.utils.escape_markdown(discord.utils.escape_mentions(ln)) for ln in lines)
    return "\n".join(f"> *{ln}*" for ln in safe)


def render_review(row) -> str:
    head = f"{stars(row['rating'])} — <@{row['author_id']}> ({row['date']})"
    if row["comment"]:
        quote = _quote(row["comment"])
        if quote:
            return f"{head}\n{quote}\n"
    return head


async def build_reviews_page(db, support_id: int, name: str, page: int):
    """Возвращает (embed, view) для страницы отзывов (нумерация страниц с 0)."""
    total = await db.count_reviews(support_id)
    pages = max(1, math.ceil(total / config.REVIEWS_PER_PAGE))
    page = min(max(page, 0), pages - 1)
    rows = await db.get_reviews(support_id, config.REVIEWS_PER_PAGE, page * config.REVIEWS_PER_PAGE)

    description = "\n".join(render_review(r) for r in rows).strip() or "Отзывов пока нет."
    if len(description) > 4096:
        description = description[:4093] + "…"

    embed = discord.Embed(
        title=f"📋 Отзывы о {name}",
        description=description,
        color=config.COLOR_BLURPLE,
    )
    embed.set_footer(text=f"Страница {page + 1}/{pages} • Всего: {total}")
    return embed, ReviewsView(support_id, name, page, pages)


class ReviewsView(discord.ui.View):
    def __init__(self, support_id: int, name: str, page: int, pages: int) -> None:
        super().__init__(timeout=600)
        self.support_id = support_id
        self.name = name
        self.page = page
        self.pages = pages
        self.prev_button.disabled = page <= 0
        self.next_button.disabled = page >= pages - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._turn(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._turn(interaction, self.page + 1)

    async def _turn(self, interaction: discord.Interaction, page: int) -> None:
        embed, view = await build_reviews_page(interaction.client.db, self.support_id, self.name, page)
        await interaction.response.edit_message(embed=embed, view=view)


# ═══════════════════════════════ Профиль ═══════════════════════════════
async def build_profile_embed(db, member) -> discord.Embed:
    now = int(time.time())
    day_acc, day_den = await db.count_actions(member.id, now - DAY)
    week_acc, week_den = await db.count_actions(member.id, now - 7 * DAY)
    month_acc, month_den = await db.count_actions(member.id, now - 30 * DAY)
    all_acc, all_den = await db.count_actions(member.id)
    voice_seconds = await db.get_voice_time(member.id)
    avg, reviews_count = await db.get_rating(member.id)

    embed = discord.Embed(
        title=f"👤 Профиль саппорта · {member.display_name}",
        color=config.COLOR_BLURPLE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    def period(accepted: int, denied: int) -> str:
        return f"\n• Верификации: **{accepted}**\n• Недопущено: **{denied}**"

    embed.add_field(name="📅 За сутки", value=period(day_acc, day_den), inline=True)
    embed.add_field(name="📅 За неделю", value=period(week_acc, week_den), inline=True)
    embed.add_field(name="🗓️ За месяц", value=period(month_acc, month_den), inline=True)
    embed.add_field(
        name="📊 За всё время",
        value=(
            f"• Верификации: **{all_acc}**\n"
            f"• Недопущено: **{all_den}**\n"
            f"• Время в проходной: **{format_duration(voice_seconds)}**"
        ),
        inline=False,
    )
    avg_text = f"{avg:.1f}" if avg is not None else "—"
    embed.add_field(
        name="⭐ Рейтинг",
        value=f"Средняя оценка: **{avg_text}** ⭐\nВсего отзывов: **{reviews_count}**",
        inline=False,
    )
    embed.set_footer(text=f"ID: {member.id}")
    return embed


class ProfileView(discord.ui.View):
    def __init__(self, support_id: int, name: str) -> None:
        super().__init__(timeout=600)
        self.support_id = support_id
        self.name = name

    @discord.ui.button(label="Просмотреть отзывы верификации", style=discord.ButtonStyle.primary)
    async def show_reviews(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        db = interaction.client.db
        if await db.count_reviews(self.support_id) == 0:
            await interaction.response.send_message("📭 У этого саппорта пока нет отзывов.", ephemeral=True)
            return
        embed, view = await build_reviews_page(db, self.support_id, self.name, 0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ═════════════════════════════════ Cog ═════════════════════════════════
class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="support_top", description="Топ активности саппортов")
    @app_commands.guild_only()
    async def support_top(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.get_top()

        lines: list[str] = []
        size = 0
        for place, row in enumerate(rows, start=1):
            line = (
                f"{place}. <@{row['support_id']}> — принято: **{row['accepted']}**, "
                f"отказано: **{row['denied']}** (всего *{row['total']}*)"
            )
            if size + len(line) + 1 > 4000:  # лимит описания embed — 4096
                break
            lines.append(line)
            size += len(line) + 1

        embed = discord.Embed(
            title="📊 Активность саппортов",
            description="\n".join(lines) if lines else "Пока нет данных о проверках.",
            color=config.COLOR_GOLD,
        )
        if len(lines) < len(rows):
            embed.set_footer(text=f"Показаны первые {len(lines)} из {len(rows)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="support_profile", description="Профиль саппорта со статистикой и отзывами"
    )
    @app_commands.describe(member="Саппорт, чей профиль нужно показать")
    @app_commands.guild_only()
    async def support_profile(self, interaction: discord.Interaction, member: discord.Member) -> None:
        db = self.bot.db
        if member.bot or not (is_staff(member) or await db.has_activity(member.id)):
            await interaction.response.send_message(
                "ℹ️ Этот пользователь не является саппортом.", ephemeral=True
            )
            return

        embed = await build_profile_embed(db, member)
        view = ProfileView(member.id, member.display_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
