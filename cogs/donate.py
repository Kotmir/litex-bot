import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# Константы настроек
CATEGORY_ID = 1565544404297457744  # ID категории для тикетов доната
TARGET_USER_ID = 393700489881190411  # Необходимый пользователь для пинга
EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)  # Розово-фиолетовый цвет Litex
IMAGE_URL = "https://cdn.discordapp.com/attachments/1564805779561783296/1565544881550786631/83960ce0-5862-40fd-9318-29d1fe411425.png?ex=6ae54aca&is=6ae3f94a&hm=6df4c8933d8f50b8896876606f1793419a32881abea1449fa0a0ea71f3cda748&"
SPACER_URL = "https://raw.githubusercontent.com/Androz2091/AtlantaBot/master/assets/img/invisible.png"

class PrimeSelect(discord.ui.Select):
    """Выпадающее меню для выбора срока подписки Prime"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label="30 дней — 150 коинов",
                description="Стандартная подписка на 1 месяц",
                emoji="⏳",
                value="30"
            ),
            discord.SelectOption(
                label="90 дней — 400 коинов (Выгодно)",
                description="Сэкономьте при покупке на 3 месяца",
                emoji="🔥",
                value="90"
            ),
            discord.SelectOption(
                label="180 дней — 700 коинов (Максимальная выгода)",
                description="Получите максимум привилегий на полгода",
                emoji="💎",
                value="180"
            ),
        ]
        super().__init__(
            placeholder="✨ Выберите срок подписки Prime...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="prime_duration_select"
        )

    async def callback(self, interaction: discord.Interaction):
        days = self.values[0]
        prices = {
            "30": "150 коинов",
            "90": "400 коинов",
            "180": "700 коинов"
        }
        
        embed = discord.Embed(
            title=f"🛒 Вы выбрали подписку Prime ({days} дней)",
            description=(
                f"💰 Стоимость: **{prices.get(days)}**\n\n"
                "📌 **Что делать дальше?**\n"
                "> Нажмите кнопку **«Создать тикет для покупки»** ниже, чтобы открыть личный диалог с администрацией и завершить оформление."
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Проект Litex • Магазин привилегий")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await interaction.message.edit(view=PrimeView())
        except discord.HTTPException:
            pass


class CloseDonateTicketView(discord.ui.View):
    """Панель закрытия тикета доната"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_donate_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("⛔ Закрывать тикеты могут только администраторы.", ephemeral=True)
        
        await interaction.response.send_message("🔒 Тикет будет удален через 5 секунд...")
        await asyncio.sleep(5)
        if interaction.channel:
            await interaction.channel.delete()


class PrimeView(discord.ui.View):
    """Панель с выпадающим меню и кнопкой создания тикета"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PrimeSelect())

    @discord.ui.button(label="Создать тикет для покупки", style=discord.ButtonStyle.success, emoji="🎫", custom_id="buy_prime_ticket_btn")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        if not guild:
            return

        category = guild.get_channel(CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.followup.send(
                "❌ Ошибка: Категория для тикетов доната не найдена. Обратитесь к администратору.",
                ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        channel_name = f"донат-{interaction.user.name}"
        ticket_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        embed = discord.Embed(
            title="👑 Покупка подписки Prime",
            description=(
                f"Здравствуйте, {interaction.user.mention}!\n\n"
                "Укажите срок подписки, которую вы хотите приобрести, и способ оплаты (или обратитесь к **@AllCash**).\n"
                "Администратор ответит вам в ближайшее время!"
            ),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Проект Litex • Отдел продаж")

        ping_content = f"🔔 {interaction.user.mention} <@{TARGET_USER_ID}> | Администрация скоро свяжется с вами."

        await ticket_channel.send(
            content=ping_content,
            embed=embed,
            view=CloseDonateTicketView(),
            allowed_mentions=discord.AllowedMentions(users=True)
        )
        
        await interaction.followup.send(
            f"✅ Тикет успешно создан! Перейдите в канал {ticket_channel.mention}.",
            ephemeral=True
        )


class DonateSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(PrimeView())
        self.bot.add_view(CloseDonateTicketView())

    @app_commands.command(
        name="setup_donat",
        description="Установить панель покупки доната и подписки Prime (Только для Администрации)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_donat(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        banner_embed = discord.Embed(color=EMBED_COLOR)
        banner_embed.set_image(url=IMAGE_URL.strip())

        info_embed = discord.Embed(
            title="👑 Подписка Prime",
            description=(
                "Получите максимальный набор привилегий и возможностей для комфортной игры на сервере по выгодной цене!\n\n"
                "💰 **Стоимость подписки:**\n"
                "> • **30 дней:** `150 коинов`\n"
                "> • **90 дней:** `400 коинов` *(Выгодно)*\n"
                "> • **180 дней:** `700 коинов` *(Максимальная выгода)*"
            ),
            color=EMBED_COLOR,
        )
        info_embed.set_image(url=SPACER_URL)

        features_embed = discord.Embed(
            title="🛠️ Функционал и команды Prime:",
            description=(
                "**✨ Кастомизация и предметы:**\n"
                "> • Надевание любого предмета на голову — `/hat`\n"
                "> • Переименование предметов на наковальне с цветами (`&x`)\n"
                "> • Добавление описания (лора) предметам — `/ie lore`\n\n"
                "**⭐ Опыт и чат:**\n"
                "> • Перевод опыта в бутыльки — `/expbottle`\n"
                "> • Покраска сообщений в чате через `<color>`\n"
                "> • Бесплатный супер-префикс перед ником\n\n"
                "**💬 Твинки и Discord:**\n"
                "> • Создание до **2 мульти-аккаунтов** (твинков)\n"
                "> • Личный стикер в Discord-сервере\n\n"
                "**🏛️ Привилегии сервера:**\n"
                "> • Приоритетное рассмотрение идей Администрацией\n"
                "> • Доступ к эксклюзивному чату донатеров (`💬・чат-донатеров`)\n\n"
                "──────────────────────────────\n"
                "📌 *По всем вопросам обращайтесь к **@AllCash** или создайте тикет.*"
            ),
            color=EMBED_COLOR,
        )
        features_embed.set_image(url=SPACER_URL)
        features_embed.set_footer(text="Проект Litex • Магазин привилегий")

        await interaction.channel.send(
            embeds=[banner_embed, info_embed, features_embed],
            view=PrimeView(),
        )
        await interaction.followup.send("✅ Панель покупки подписки Prime успешно установлена!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DonateSetup(bot))