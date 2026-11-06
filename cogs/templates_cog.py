import discord
from discord import app_commands
from discord.ext import commands

# Роли с доступом к шпаргалке (Практиканты, Хелперы, Модераторы/Адм)
ALLOWED_ROLES = [
    1566325500157366333,
    1535921559955574908,
    1535921559955574909,
]

COLOR_EMBED = 0xEC4899  # Фирменный цвет Litex

# База всех шаблонов
TEMPLATES = {
    "1": {
        "title": "1. Заявка на рассмотрении",
        "emoji": "📘",
        "short": "Приглашение в голосовой канал «📘・Проверка 1»",
        "text": (
            "@пинг\n"
            "Здравствуйте! Ваша заявка находится на рассмотрении.\n"
            "Пожалуйста, зайдите в голосовой канал «📘・Проверка 1» для продолжения."
        ),
        "extra": None,
    },
    "2": {
        "title": "2. Напоминание / уточнение времени",
        "emoji": "⏰",
        "short": "Уточнение времени проверки (таймер 24 часа)",
        "text": (
            "@пинг\n"
            "В какое время вам удобно пройти проверку?\n"
            "Если в течение 24 часов не будет ответа — тикет будет закрыт.\n"
            "Вы сможете переподать заявку, когда вам будет удобно."
        ),
        "extra": None,
    },
    "3": {
        "title": "3. Заявка одобрена",
        "emoji": "✅",
        "short": "Одобрение заявки + команда вайтлиста",
        "text": (
            "@пинг\n"
            "Поздравляем! Ваша заявка одобрена\n"
            "Вы добавлены в белый список.\n"
            "Приятной игры и удачи на сервере!"
        ),
        "extra": "/swlt add ник -1",
    },
    "4": {
        "title": "4. Заявка отклонена",
        "emoji": "❌",
        "short": "Вежливый отказ в заявке",
        "text": (
            "@пинг\n"
            "К сожалению, ваша заявка была отклонена.\n"
            "Спасибо за интерес к проекту. Всего доброго!"
        ),
        "extra": None,
    },
    "5": {
        "title": "5. Заявка заморожена",
        "emoji": "❄️",
        "short": "Временная приостановка заявки до готовности игрока",
        "text": (
            "@пинг\n"
            "Здравствуйте! Обработка вашей заявки временно приостановлена.\n"
            "Когда будете готовы пройти проверку — напишите в этот тикет.\n"
            "Мы продолжим с того места, где остановились."
        ),
        "extra": None,
    },
    "6": {
        "title": "6. Аккаунт не соответствует требованиям",
        "emoji": "⚠️",
        "short": "Отказ по возрасту (<13 лет) или дате создания Discord (<7 дней)",
        "text": (
            "@пинг\n"
            "Привет! К сожалению, твой аккаунт не соответствует требованиям сервера.\n"
            "Требования:\n"
            "— Возраст от 13 лет\n"
            "— Аккаунту Discord больше 7 дней"
        ),
        "extra": None,
    },
    "7": {
        "title": "7. Если не хотят качать сборку (основные моды)",
        "emoji": "🧩",
        "short": "Список обязательных модов для игры на сервере",
        "text": (
            "@пинг\n"
            "Для игры на сервере обязательны следующие моды:\n"
            "— Simple Voice\n"
            "— Custom Player Models\n"
            "— Emote Craft\n"
            "— Female Gender Mod\n"
            "— Pat Pat\n\n"
            "Установи их, пожалуйста, чтобы продолжить проверку."
        ),
        "extra": None,
    },
    "8": {
        "title": "8. Закрытие тикета за ожидание (альтернатива)",
        "emoji": "🔒",
        "short": "Закрытие тикета после 24 часов без ответа",
        "text": (
            "@пинг\n"
            "Так как в течение 24 часов ответа не поступило — тикет закрывается.\n"
            "Вы сможете подать заявку снова в любое удобное время."
        ),
        "extra": None,
    },
}


def build_all_templates_embed() -> discord.Embed:
    """Создает главный Embed со всеми шаблонами сразу."""
    embed = discord.Embed(
        title="🌸 Шпаргалка по ответам в тикетах • Litex",
        description=(
            "Ниже собраны все стандартные шаблоны ответов для проверки заявок.\n"
            "💡 *Выберите нужный пункт в меню ниже, чтобы удобно скопировать текст в 1 клик!*"
        ),
        color=COLOR_EMBED,
    )

    for key, item in TEMPLATES.items():
        value_text = f"```txt\n{item['text']}```"
        if item["extra"]:
            value_text += f"**Команда для сервера:**\n```txt\n{item['extra']}```"

        embed.add_field(
            name=f"{item['emoji']} {item['title']}",
            value=value_text,
            inline=False,
        )

    embed.set_footer(text="Litex Staff Helper • Доступно только персоналу сервера")
    return embed


def build_single_template_embed(key: str) -> discord.Embed:
    """Создает Embed для конкретного выбранного шаблона."""
    item = TEMPLATES[key]
    embed = discord.Embed(
        title=f"{item['emoji']} {item['title']}",
        description=(
            "**Готовый текст для отправки в тикет** *(нажмите кнопку копирования в углу блока)*:\n"
            f"```txt\n{item['text']}```"
        ),
        color=COLOR_EMBED,
    )

    if item["extra"]:
        embed.add_field(
            name="💻 Команда добавления в вайтлист:",
            value=f"```txt\n{item['extra']}```",
            inline=False,
        )

    embed.set_footer(text="Не забудьте заменить @пинг на упоминание игрока!")
    return embed


class TemplateSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Показать все шаблоны сразу",
                description="Вернуться к общему списку всех 8 шаблонов",
                emoji="📋",
                value="all",
            )
        ]

        for key, item in TEMPLATES.items():
            options.append(
                discord.SelectOption(
                    label=item["title"],
                    description=item["short"],
                    emoji=item["emoji"],
                    value=key,
                )
            )

        super().__init__(
            placeholder="🔍 Выберите шаблон для быстрого копирования...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        choice = self.values[0]
        if choice == "all":
            embed = build_all_templates_embed()
        else:
            embed = build_single_template_embed(choice)

        await interaction.response.edit_message(embed=embed, view=self.view)


class TemplateView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=900)  # Меню активно 15 минут
        self.add_item(TemplateSelect())


class StaffTemplatesCog(commands.Cog):
    """Шпаргалка с шаблонами ответов для практикантов, хелперов и администрации."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="templates",
        description="Шпаргалка с готовыми шаблонами ответов для тикетов"
    )
    @app_commands.guild_only()
    async def templates_cmd(self, interaction: discord.Interaction) -> None:
        # Проверка прав доступа
        if not isinstance(interaction.user, discord.Member):
            return

        has_role = any(role.id in ALLOWED_ROLES for role in interaction.user.roles)
        is_admin = interaction.user.guild_permissions.administrator

        if not (has_role or is_admin):
            await interaction.response.send_message(
                "❌ **У вас нет доступа к этой команде!** Шпаргалка доступна только персоналу сервера.",
                ephemeral=True,
            )
            return

        embed = build_all_templates_embed()
        await interaction.response.send_message(
            embed=embed,
            view=TemplateView(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StaffTemplatesCog(bot))