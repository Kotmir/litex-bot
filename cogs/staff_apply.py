import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# Константы настроек
CATEGORY_ID = 1565495732067369061
EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)  # Розово-фиолетовый цвет
IMAGE_URL = "https://cdn.discordapp.com/attachments/1564805779561783296/1565494456302440519/dd1d23d3-47ea-4d4e-9507-3f023d800cf4.png?ex=6ae51bd3&is=6ae3ca53&hm=e3462377d0c2bb2bc0f05cf31014a4e9f95b98217ea23fd637248836ee94c7ac&"
# Невидимая линия-распорка, чтобы все эмбеды имели одинаковую ровную правую границу
SPACER_URL = "https://raw.githubusercontent.com/Androz2091/AtlantaBot/master/assets/img/invisible.png"

# Индивидуальные вопросы и примеры для каждого направления
ROLE_QUESTIONS = {
    "Состав": [
        {
            "label": "Ваше имя, возраст и часовой пояс",
            "placeholder": "Иван, 17 лет, МСК (UTC+3)",
            "style": discord.TextStyle.short,
            "max_length": 60,
        },
        {
            "label": "Опыт модерирования и знание правил",
            "placeholder": "Был модератором на проекте ХХХ полгода, отлично знаю механики и правила...",
            "style": discord.TextStyle.paragraph,
            "max_length": 1000,
        },
        {
            "label": "Сколько времени готовы уделять проекту?",
            "placeholder": "3-5 часов в день, преимущественно вечером",
            "style": discord.TextStyle.short,
            "max_length": 100,
        },
        {
            "label": "Почему именно вы и ваши сильные стороны?",
            "placeholder": "Стрессоустойчив, быстро разбираюсь в спорных ситуациях...",
            "style": discord.TextStyle.paragraph,
            "max_length": 1000,
        },
    ],
    "Контент-мейкеры": [
        {
            "label": "Ваше имя, возраст и никнейм",
            "placeholder": "Алексей, 18 лет, Ник: AlexPlay",
            "style": discord.TextStyle.short,
            "max_length": 60,
        },
        {
            "label": "Ссылки на ваши каналы (YouTube, Twitch, TT)",
            "placeholder": "youtube.com/@... , twitch.tv/...",
            "style": discord.TextStyle.paragraph,
            "max_length": 500,
        },
        {
            "label": "Статистика и формат контента",
            "placeholder": "Стримы по выживанию (онлайн 30+), Shorts/TikTok (в среднем по 5к просмотров)",
            "style": discord.TextStyle.paragraph,
            "max_length": 800,
        },
        {
            "label": "Как часто планируете выпускать контент?",
            "placeholder": "2-3 ролика в неделю и стримы по выходным",
            "style": discord.TextStyle.short,
            "max_length": 150,
        },
    ],
    "Роли в государстве": [
        {
            "label": "Имя, возраст и желаемая должность",
            "placeholder": "Дмитрий, 16 лет | Судья / Министр / Мэр",
            "style": discord.TextStyle.short,
            "max_length": 80,
        },
        {
            "label": "Опыт участия в РП и гос. структурах",
            "placeholder": "Занимал пост главы города на прошлом сезоне, организовывал суды и ивенты...",
            "style": discord.TextStyle.paragraph,
            "max_length": 1000,
        },
        {
            "label": "Ваши идеи по развитию государства и РП",
            "placeholder": "Хочу ввести систему экономики, проводить еженедельные собрания и...",
            "style": discord.TextStyle.paragraph,
            "max_length": 1000,
        },
        {
            "label": "Ваш средний онлайн на сервере",
            "placeholder": "От 4 часов в день",
            "style": discord.TextStyle.short,
            "max_length": 100,
        },
    ],
}


class ApplyModal(discord.ui.Modal):
    """Динамическое модальное окно с анкетой под выбранное направление"""
    def __init__(self, role_name: str):
        super().__init__(title=f"Анкета: {role_name}"[:45])
        self.role_name = role_name
        self.inputs: list[tuple[str, discord.ui.TextInput]] = []

        questions = ROLE_QUESTIONS.get(role_name, ROLE_QUESTIONS["Состав"])

        for q in questions:
            label_text = q["label"][:45]
            text_input = discord.ui.TextInput(
                label=label_text,
                placeholder=q["placeholder"][:100],
                style=q["style"],
                min_length=2,
                max_length=q["max_length"],
                required=True,
            )
            self.inputs.append((label_text, text_input))
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(CATEGORY_ID)

        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.followup.send(
                "❌ Ошибка: Категория для тикетов не найдена. Обратитесь к администратору.",
                ephemeral=True,
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
            ),
        }

        channel_name = f"заявка-{interaction.user.name}"
        ticket_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        answers_text = "\n\n".join(
            f"🔹 **{idx}. {label_text}:**\n```\n{item.value.replace('```', '')}\n```"
            for idx, (label_text, item) in enumerate(self.inputs, start=1)
        )

        embed = discord.Embed(
            title=f"📥 Новая заявка: {self.role_name}",
            description=(
                f"👤 **Кандидат:** {interaction.user.mention} (`{interaction.user.id}`)\n\n"
                f"{answers_text}"
            ),
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(
            text="Проект Litex • Набор в отделы",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        await ticket_channel.send(
            content=f"🔔 {interaction.user.mention} | Администрация скоро рассмотрит вашу заявку.",
            embed=embed,
            view=CloseTicketView(),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        await interaction.followup.send(
            f"✅ Ваша заявка успешно создана в канале {ticket_channel.mention}!",
            ephemeral=True,
        )


class ConfirmCloseView(discord.ui.View):
    """Панель подтверждения закрытия тикета"""
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Да, закрыть тикет", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            content="🔒 Закрытие и удаление канала через 5 секунд...",
            view=self,
        )
        await asyncio.sleep(5)
        if interaction.channel:
            await interaction.channel.delete()

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ Закрытие тикета отменено.",
            view=None,
        )


class CloseTicketView(discord.ui.View):
    """Панель управления внутри тикета (закрытие)"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Закрыть тикет",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket_btn",
        emoji="🔒",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Только администраторы могут закрывать тикеты заявлений.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "⚠️ **Вы уверены, что хотите закрыть и удалить этот тикет?**",
            view=ConfirmCloseView(),
            ephemeral=True,
        )


class ApplicationDropdown(discord.ui.Select):
    """Выпадающее меню выбора направления"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Набор в состав",
                description="Подать заявку на модератора, хелпера или куратора",
                emoji="🛡️",
                value="Состав",
            ),
            discord.SelectOption(
                label="Набор в контент-мейкеров",
                description="Для стримеров, ютуберов и тиктокеров",
                emoji="🎥",
                value="Контент-мейкеры",
            ),
            discord.SelectOption(
                label="Набор на роли в государстве",
                description="Подать заявку на судью, министра, мэра или участника гос. структур",
                emoji="🏛️",
                value="Роли в государстве",
            ),
        ]
        super().__init__(
            placeholder="🟣 Выберите направление заявки",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="staff_apply_select",
        )

    async def callback(self, interaction: discord.Interaction):
        role_name = self.values[0]
        await interaction.response.send_modal(ApplyModal(role_name))
        # Сбрасываем выбранный пункт на панели, чтобы плейсхолдер оставался чистым
        try:
            await interaction.message.edit(view=ApplicationView())
        except discord.HTTPException:
            pass


class ApplicationView(discord.ui.View):
    """Постоянная панель с выпадающим меню"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApplicationDropdown())


class StaffApply(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(ApplicationView())
        self.bot.add_view(CloseTicketView())

    @app_commands.command(
        name="setup_staff_apply",
        description="Установить панель подачи заявок на роли (Только для Администрации)",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_staff_apply(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # 1. Верхний эмбед — баннер
        banner_embed = discord.Embed(color=EMBED_COLOR)
        banner_embed.set_image(url=IMAGE_URL.strip())

        # 2. Средний эмбед — блок с требованиями (с ровной правой границей)
        req_embed = discord.Embed(
            title="📋 Набор в команду проекта Litex",
            description=(
                "**Минимальные требования для кандидатов в состав:**\n"
                "```diff\n- Несоответствие любому пункту = автоматический отказ!\n```\n"
                "> 🔞 **Возраст:** строго от `16+ лет` (без исключений)\n"
                "> 🎙️ **Периферия:** исправный микрофон для голосовых чатов\n"
                "> 🧠 **Качества:** адекватность, грамотность и стрессоустойчивость\n"
                "> 🛠️ **Знания:** механики игры, правила сервера и `CoreProtect`"
            ),
            color=EMBED_COLOR,
        )
        req_embed.set_image(url=SPACER_URL)

        # 3. Нижний эмбед — выбор отдела (без времени отправки и с ровной границей)
        main_embed = discord.Embed(
            title="✨ Добро пожаловать в набор в отделы",
            description=(
                "**Подай заявку в нужный отдел проекта:**\n\n"
                "> 🛡️ **Набор в состав** — хелперы, модерация и кураторы\n"
                "> 🎥 **Набор в контент-мейкеров** — YouTube, Twitch и TikTok\n"
                "> 🏛️ **Набор на роли в государстве** — лидеры и РП-структуры\n\n"
                "📌 **Как это работает**\n"
                "```\nВыбери направление ниже и заполни короткую анкету.```\n"
                "⏳ **Срок рассмотрения**\n"
                "```\nЗаявки рассматриваются в течение 3-х дней.```"
            ),
            color=EMBED_COLOR,
        )
        main_embed.set_image(url=SPACER_URL)
        main_embed.set_footer(
            text="Проект Litex • Набор в отделы",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        await interaction.channel.send(
            embeds=[banner_embed, req_embed, main_embed],
            view=ApplicationView(),
        )
        await interaction.followup.send("✅ Панель подачи заявок успешно создана!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffApply(bot))