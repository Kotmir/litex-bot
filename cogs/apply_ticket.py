import datetime
import html
import json
import os
import re
from collections import Counter
import discord
from discord import app_commands
from discord.ext import commands

# ID роли игрока сервера (если она есть — тикет создать нельзя)
PLAYER_ROLE_ID = 1535921559955574907

# ID роли, необходимой для подачи тикета (если её нет — тикет создать нельзя)
APPLICANT_ROLE_ID = 1559508180868796556

# Роли модераторов/администраторов (доступ к тикету + ПРАВО ЗАКРЫВАТЬ)
STAFF_ROLES = [1535921559955574908, 1535921559955574909]

# Роли с доступом к тикету и переписке, но БЕЗ права закрывать тикеты
TICKET_VIEW_ROLES = [1566325500157366333]

# Ссылки на каналы правил и информации
RULES_CHANNEL_ID = 1567041822704803860
INFO_CHANNEL_ID = 1567041297209102458

# ID канала для отправки транскриптов
TRANSCRIPT_CHANNEL_ID = 1567044449505255434

# ID категории, куда будут создаваться тикеты
TICKET_CATEGORY_ID = 1535921560508960838

COLOR_EMBED = 0xEC4899       # Фирменный цвет Litex
COLOR_TRANSCRIPT = 0x2ECC71  # Зеленый цвет для карточки лога транскрипта

# Файл для хранения счетчика тикетов (чтобы не сбрасывался после удаления канала)
COUNTER_FILE = "ticket_counter.json"


def get_next_ticket_number() -> int:
    """Возвращает следующий номер тикета начиная с 0 (0000, 0001, 0002...) и сохраняет его."""
    last_num = -1
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_num = data.get("last_ticket", -1)
        except Exception:
            last_num = -1

    next_num = last_num + 1
    try:
        with open(COUNTER_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_ticket": next_num}, f)
    except Exception:
        pass

    return next_num


def format_user_tag(user: discord.abc.User) -> str:
    """Форматирует тег пользователя как на скриншоте (с #0 для новых аккаунтов)."""
    if getattr(user, "discriminator", "0") in ("0", "0000", None, ""):
        return f"{user.name}#0"
    return f"{user.name}#{user.discriminator}"


# --- КЛАСС ПОДТВЕРЖДЕНИЯ ЗАКРЫТИЯ ТИКЕТА ---
class ConfirmCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=60)

    @discord.ui.button(label="Подтвердить закрытие", style=discord.ButtonStyle.danger, emoji="✔️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        has_permission = (
            any(role.id in STAFF_ROLES for role in interaction.user.roles)
            or interaction.user.guild_permissions.administrator
        )
        if not has_permission:
            await interaction.response.send_message("❌ У вас нет прав на закрытие этого тикета!", ephemeral=True)
            return

        channel = interaction.channel
        guild = interaction.guild

        await interaction.response.send_message("🔒 Закрываем заявку и формируем транскрипт...", ephemeral=True)

        # Определяем владельца тикета из topic канала
        owner_id = None
        if channel.topic:
            match = re.search(r"ID:\s*(\d+)", channel.topic)
            if match:
                owner_id = int(match.group(1))

        ticket_owner = guild.get_member(owner_id) if owner_id else None
        if not ticket_owner and owner_id:
            try:
                ticket_owner = await interaction.client.fetch_user(owner_id)
            except Exception:
                ticket_owner = None

        # 1. Собираем историю сообщений и считаем статистику участников
        messages_history = []
        user_counts: Counter[int] = Counter()
        user_objects: dict[int, discord.abc.User] = {}

        async for message in channel.history(limit=500, oldest_first=True):
            user_counts[message.author.id] += 1
            user_objects[message.author.id] = message.author

            timestamp = message.created_at.strftime("%d.%m.%Y %H:%M")
            parts = []
            if message.content:
                parts.append(html.escape(message.content))

            for emb in message.embeds:
                emb_text = []
                if emb.title:
                    emb_text.append(f"<b>{html.escape(emb.title)}</b>")
                if emb.description:
                    emb_text.append(html.escape(emb.description))
                if emb_text:
                    parts.append("<div class='embed'>" + "<br>".join(emb_text) + "</div>")

            if message.attachments:
                for att in message.attachments:
                    parts.append(
                        f"<a href='{att.url}' style='color: #00a8fc;' target='_blank'>[Вложение: {html.escape(att.filename)}]</a>"
                    )

            content_html = "<br>".join(parts) if parts else "[Пустое сообщение]"

            messages_history.append({
                "author": html.escape(message.author.display_name),
                "tag": html.escape(format_user_tag(message.author)),
                "avatar": message.author.display_avatar.url,
                "content": content_html,
                "timestamp": timestamp,
                "is_bot": message.author.bot
            })

        closed_name = (
            channel.name.replace("ticket-", "closed-")
            if channel.name.startswith("ticket-")
            else f"closed-{channel.name}"
        )

        # 2. Генерируем HTML-код транскрипта
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Транскрипт: {closed_name}</title>
            <style>
                body {{ background-color: #313338; color: #dbdee1; font-family: 'gg sans', 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 880px; margin: 0 auto; }}
                .header {{ background-color: #2b2d31; padding: 20px 25px; border-radius: 10px; border-left: 4px solid #ec4899; margin-bottom: 20px; }}
                .header h2 {{ margin: 0 0 8px 0; color: #f2f3f5; font-size: 20px; }}
                .header p {{ margin: 0; color: #949ba4; font-size: 13px; }}
                .chat {{ display: flex; flex-direction: column; gap: 4px; }}
                .message {{ display: flex; padding: 10px 16px; border-radius: 6px; }}
                .message:hover {{ background-color: #2e3035; }}
                .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 16px; flex-shrink: 0; }}
                .msg-body {{ flex: 1; min-width: 0; }}
                .author-line {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
                .author {{ font-weight: 600; color: #f2f3f5; font-size: 15px; }}
                .bot-tag {{ background-color: #5865f2; color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 3px; font-weight: 600; }}
                .time {{ font-size: 11px; color: #949ba4; }}
                .content {{ color: #dbdee1; font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-wrap: break-word; }}
                .embed {{ background-color: #2b2d31; border-left: 4px solid #ec4899; padding: 12px; border-radius: 4px; margin-top: 6px; max-width: 520px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📁 Транскрипт заявки #{closed_name}</h2>
                    <p>Сервер: <b>{html.escape(guild.name)}</b> • Закрыл: <b>{html.escape(format_user_tag(interaction.user))}</b> • Дата: <b>{datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}</b></p>
                </div>
                <div class="chat">
        """

        for msg in messages_history:
            bot_badge = '<span class="bot-tag">БОТ</span>' if msg["is_bot"] else ""
            html_content += f"""
                    <div class="message">
                        <img class="avatar" src="{msg['avatar']}" alt="avatar">
                        <div class="msg-body">
                            <div class="author-line">
                                <span class="author">{msg['author']}</span>
                                {bot_badge}
                                <span class="time">{msg['timestamp']}</span>
                            </div>
                            <div class="content">{msg['content']}</div>
                        </div>
                    </div>
            """

        html_content += """
                </div>
            </div>
        </body>
        </html>
        """

        # 3. Сохраняем во временный файл
        filename = f"transcript-{closed_name}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 4. Отправляем карточку лога в канал транскриптов
        transcript_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
        if transcript_channel:
            owner_user = ticket_owner or interaction.user
            embed_log = discord.Embed(color=COLOR_TRANSCRIPT)
            embed_log.set_author(
                name=format_user_tag(owner_user),
                icon_url=owner_user.display_avatar.url
            )

            embed_log.add_field(
                name="Ticket Owner",
                value=owner_user.mention if ticket_owner else f"<@{owner_id}>" if owner_id else interaction.user.mention,
                inline=True
            )
            embed_log.add_field(
                name="Ticket Name",
                value=closed_name,
                inline=True
            )
            embed_log.add_field(
                name="Panel Name",
                value="Заявки на сервер",
                inline=True
            )
            embed_log.add_field(
                name="Direct Transcript",
                value="Use Button",
                inline=True
            )

            users_lines = []
            for uid, count in user_counts.most_common():
                u_obj = user_objects[uid]
                users_lines.append(f"{count} - {u_obj.mention} ({format_user_tag(u_obj)})")
            users_value = "\n".join(users_lines) if users_lines else "Нет сообщений"

            embed_log.add_field(
                name="Users in transcript",
                value=users_value[:1024],
                inline=True
            )

            file = discord.File(filename)
            sent_msg = await transcript_channel.send(embed=embed_log, file=file)

            if sent_msg.attachments:
                link_view = discord.ui.View()
                link_view.add_item(
                    discord.ui.Button(
                        label="Direct Transcript",
                        style=discord.ButtonStyle.link,
                        url=sent_msg.attachments[0].url,
                        emoji="📄"
                    )
                )
                await sent_msg.edit(view=link_view)

        if os.path.exists(filename):
            os.remove(filename)

        await channel.delete(reason=f"Заявка закрыта пользователем {interaction.user}")

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="❌ Закрытие отменено.", view=None)


# --- ПАНЕЛЬ УПРАВЛЕНИЯ ВНУТРИ ТИКЕТА ---
class TicketControlView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Закрыть",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_apply_ticket_btn"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Право на закрытие есть только у STAFF_ROLES и администраторов
        has_permission = (
            any(role.id in STAFF_ROLES for role in interaction.user.roles)
            or interaction.user.guild_permissions.administrator
        )
        if not has_permission:
            await interaction.response.send_message("❌ У вашей роли нет прав на закрытие тикетов!", ephemeral=True)
            return

        await interaction.response.send_message(
            "⚠️ **Подтверждение:** Вы уверены, что хотите закрыть этот тикет и сохранить транскрипт?",
            view=ConfirmCloseView(),
            ephemeral=True
        )


# --- МОДАЛЬНОЕ ОКНО С ВОПРОСАМИ ---
class ApplyModal(discord.ui.Modal, title="Заявка на сервер Litex"):
    q1 = discord.ui.TextInput(label="1. Никнейм в игре:", placeholder="Ваш игровой ник", max_length=30)
    q2 = discord.ui.TextInput(label="2. Возраст:", placeholder="Сколько вам полных лет", max_length=3)
    q3 = discord.ui.TextInput(label="3. Откуда вы узнали о сервере?", placeholder="Например: друзья, TikTok, YouTube и т.д.", max_length=100)
    q4 = discord.ui.TextInput(label="4. Сколько времени вашему Discord-аккаунту?", placeholder="Укажите, более 3 месяцев или менее", max_length=50)
    q5 = discord.ui.TextInput(label="5. Есть ли микрофон и возможность говорить?", placeholder="Да / Нет", max_length=10)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        user = interaction.user

        category = guild.get_channel(TICKET_CATEGORY_ID)

        # Получаем точный номер тикета (0000, 0001, 0002...)
        ticket_num = get_next_ticket_number()
        channel_name = f"ticket-{ticket_num:04d}"

        # Права доступа для игрока, ролей стаффа и ролей с правом просмотра
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for role_id in STAFF_ROLES + TICKET_VIEW_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                topic=f"Заявка на сервер от {user} (ID: {user.id})"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Не удалось создать канал тикета: {e}", ephemeral=True)
            return

        # Эмбед 1: Приветствие
        embed_welcome = discord.Embed(
            title="Добро пожаловать на Litex!",
            description=(
                "```\nЗаявки принимаются с 8:00 по 22:00 по МСК```\n"
                "Заявка принята в очередь на рассмотрение.\n"
                "Обычно ответ приходит в течение 1–3 часов.\n\n"
                f"👤 **Заявитель:** {user.mention}"
            ),
            color=COLOR_EMBED
        )

        # Эмбед 2: Анкета
        embed_form = discord.Embed(
            description=(
                f"**1. Никнейм в игре:** ```\n{self.q1.value}```\n"
                f"**2. Возраст:** ```\n{self.q2.value}```\n"
                f"**3. Откуда вы узнали о сервере?** ```\n{self.q3.value}```\n"
                f"**4. Сколько времени вашему Discord-аккаунту?** ```\n{self.q4.value}```\n"
                f"**5. Есть ли микрофон и возможность говорить?** ```\n{self.q5.value}```"
            ),
            color=COLOR_EMBED
        )
        embed_form.set_footer(text="Litex Ticket System")

        ping_roles = " ".join([f"<@&{role_id}>" for role_id in STAFF_ROLES + TICKET_VIEW_ROLES])
        await ticket_channel.send(
            content=f"{user.mention} {ping_roles}",
            embeds=[embed_welcome, embed_form],
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Ваша заявка успешно создана: {ticket_channel.mention}",
            ephemeral=True
        )


# --- КНОПКА СОЗДАНИЯ ТИКЕТА НА ГЛАВНОЙ ПАНЕЛИ ---
class ApplyTicketView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.primary,
        emoji="🌸",
        custom_id="create_apply_ticket_btn"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        user = interaction.user
        user_role_ids = [role.id for role in user.roles]

        # 1. Проверка: является ли пользователь уже игроком сервера (1535921559955574907)
        if PLAYER_ROLE_ID in user_role_ids:
            await interaction.response.send_message(
                "❌ **Вы уже являетесь игроком сервера!** Повторная заявка не требуется.",
                ephemeral=True
            )
            return

        # 2. Проверка: есть ли у пользователя роль для подачи тикета (1559508180868796556)
        if APPLICANT_ROLE_ID not in user_role_ids:
            await interaction.response.send_message(
                f"❌ **У вас нет роли <@&{APPLICANT_ROLE_ID}> для подачи заявки!**",
                ephemeral=True
            )
            return

        # 3. Проверка возраста аккаунта (от 7 дней)
        account_age = datetime.datetime.now(datetime.timezone.utc) - user.created_at
        if account_age.days < 7:
            await interaction.response.send_message(
                "❌ **Ваш аккаунт Discord создан менее 7 дней назад.** Подача заявки временно недоступна.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ApplyModal())


class ApplyTicketCog(commands.Cog):
    """Система тикетов для подачи заявок на сервер."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup_apply_panel",
        description="Отправить панель создания тикетов для заявок на сервер"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def setup_apply_panel(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🌸 Добро пожаловать на Litex Vanilla!",
            description=(
                "Мы рады видеть тебя здесь! Чтобы попасть на наш уютный сервер и начать выживание, "
                "оставь небольшую анкету — это займет всего пару минут.\n\n"
                "**📚 Перед подачей заявки загляни сюда:**\n"
                f"> 📜 **Правила сервера:** <#{RULES_CHANNEL_ID}>\n"
                f"> 📖 **Полезная информация:** <#{INFO_CHANNEL_ID}>\n\n"
                "**✨ Небольшие условия для вступления:**\n"
                "> • Возраст от **13 лет**\n"
                "> • Аккаунту Discord больше **7 дней**\n\n"
                "*Жми на кнопку ниже, заполняй анкету и присоединяйся к нашему комьюнити!*"
            ),
            color=COLOR_EMBED,
        )
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text="Litex • Заявки рассматриваются ежедневно с 8:00 до 22:00 по МСК")

        await interaction.channel.send(embed=embed, view=ApplyTicketView())
        await interaction.response.send_message("✅ Панель заявок успешно отправлена!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    bot.add_view(ApplyTicketView())
    bot.add_view(TicketControlView())
    await bot.add_cog(ApplyTicketCog(bot))