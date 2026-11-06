import datetime
import discord
from discord import app_commands
from discord.ext import commands

# --- НАСТРОЙКИ РОЛЕЙ (ID) ---
STAFF_MANAGERS = [
    1535717149262483567,  # Дискорд-админ
    1553471134077296791,  # Куратор команды
    1535749022537482250,  # Технический адм
    1536067549895204924   # Developer
]

ASSIGNABLE_ROLES = {
    "tech_admin": 1535749022537482250,
    "curator": 1553471134077296791,
    "discord_admin": 1535717149262483567,
    "artist": 1535626609225105458,
    "texture_packer": 1535626547283759164,
    "builder": 1536035073462378587,
    "moderator": 1536063870236364840,
    "helper": 1555332363293294692,
    "intern": 1567661522270949456
}

LOG_CHANNEL_ID = 1563550430749917344

COLOR_EMBED = 0x2b2d31
COLOR_SUCCESS = 0x2ecc71
COLOR_ERROR = 0xe74c3c


class StaffSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Технический отдел", value="tech_admin", emoji="⚙️"),
            discord.SelectOption(label="Куратор состава", value="curator", emoji="🟤"),
            discord.SelectOption(label="Дискорд-админ", value="discord_admin", emoji="🛡️"),
            discord.SelectOption(label="Художник", value="artist", emoji="🎨"),
            discord.SelectOption(label="Текстур-пакер", value="texture_packer", emoji="🖌️"),
            discord.SelectOption(label="Билдер", value="builder", emoji="🧱"),
            discord.SelectOption(label="Модератор", value="moderator", emoji="🔨"),
            discord.SelectOption(label="Хелпер", value="helper", emoji="🔰"),
            discord.SelectOption(label="Практикант", value="intern", emoji="🎓"),
        ]
        super().__init__(
            placeholder="Выберите роль для управления...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="select_staff_role_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_role_key = self.values[0]
        selected_option = next(opt for opt in self.options if opt.value == self.values[0])
        
        await interaction.response.send_message(
            f"✅ Вы выбрали роль: **{selected_option.label}**. Теперь выберите пользователя кнопкой ниже.", 
            ephemeral=True
        )


class StaffActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_role_key = None
        self.add_item(StaffSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not any(role.id in STAFF_MANAGERS for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав для управления составом команды!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Выдать роль (Выбрать пользователя)", style=discord.ButtonStyle.success, custom_id="btn_add_staff_role")
    async def btn_add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_role_key:
            await interaction.response.send_message("⚠️ Сначала выберите роль из выпадающего списка сверху!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "Укажите пользователя, которому нужно выдать роль:", 
            view=UserSelectView(action="add", role_key=self.selected_role_key), 
            ephemeral=True
        )

    @discord.ui.button(label="Забрать роль (Выбрать пользователя)", style=discord.ButtonStyle.danger, custom_id="btn_remove_staff_role")
    async def btn_remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_role_key:
            await interaction.response.send_message("⚠️ Сначала выберите роль из выпадающего списка сверху!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "Укажите пользователя, у которого нужно забрать роль:", 
            view=UserSelectView(action="remove", role_key=self.selected_role_key), 
            ephemeral=True
        )


class UserSelect(discord.ui.UserSelect):
    def __init__(self, action: str, role_key: str):
        super().__init__(placeholder="Выберите пользователя...", min_values=1, max_values=1)
        self.action = action
        self.role_key = role_key

    async def callback(self, interaction: discord.Interaction):
        target_member = self.values[0]
        role_id = ASSIGNABLE_ROLES[self.role_key]
        role = interaction.guild.get_role(role_id)
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        if not role:
            await interaction.response.send_message("❌ Ошибка: Роль не найдена на сервере.", ephemeral=True)
            return

        if self.action == "add":
            if role in target_member.roles:
                await interaction.response.send_message(f"❌ У {target_member.mention} уже есть эта роль.", ephemeral=True)
                return
            try:
                await target_member.add_roles(role, reason=f"Назначен пользователем {interaction.user}")
                await interaction.response.send_message(f"✅ Роль {role.mention} успешно выдана {target_member.mention}.", ephemeral=True)
                
                if log_channel:
                    embed = discord.Embed(title="🟢 Назначение в команду", color=COLOR_SUCCESS, timestamp=datetime.datetime.now())
                    embed.add_field(name="Сотрудник:", value=f"{target_member.mention} ({target_member.id})", inline=False)
                    embed.add_field(name="Должность:", value=role.mention, inline=False)
                    embed.add_field(name="Выдал:", value=interaction.user.mention, inline=False)
                    await log_channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.response.send_message("❌ У бота недостаточно прав (роль бота должна быть выше выдаваемой роли).", ephemeral=True)

        elif self.action == "remove":
            if role not in target_member.roles:
                await interaction.response.send_message(f"❌ У {target_member.mention} нет этой роли.", ephemeral=True)
                return
            try:
                await target_member.remove_roles(role, reason=f"Снята пользователем {interaction.user}")
                await interaction.response.send_message(f"✅ Роль {role.mention} успешно снята с {target_member.mention}.", ephemeral=True)
                
                if log_channel:
                    embed = discord.Embed(title="🔴 Снятие с должности", color=COLOR_ERROR, timestamp=datetime.datetime.now())
                    embed.add_field(name="Бывший сотрудник:", value=f"{target_member.mention} ({target_member.id})", inline=False)
                    embed.add_field(name="Должность:", value=role.mention, inline=False)
                    embed.add_field(name="Снял:", value=interaction.user.mention, inline=False)
                    await log_channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.response.send_message("❌ У бота недостаточно прав.", ephemeral=True)


class UserSelectView(discord.ui.View):
    def __init__(self, action: str, role_key: str):
        super().__init__(timeout=60)
        self.add_item(UserSelect(action=action, role_key=role_key))


class StaffApplyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="panel_staff", description="Отправить панель со списком команды и управлением (Только для рук-ва)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def panel_staff(self, interaction: discord.Interaction):
        if not any(role.id in STAFF_MANAGERS for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав на создание этой панели.", ephemeral=True)
            return

        embed = discord.Embed(color=COLOR_EMBED)
        description = (
            "**Роли команды Litex:**\n\n"
            "0) **Основатель проекта** - <@393700489881190411>;\n\n"
            f"1) <@&{ASSIGNABLE_ROLES['tech_admin']}> - занимается технической частью сервера в Minecraft.\n\n" 
            f"2) <@&{ASSIGNABLE_ROLES['curator']}> - следит за работой всего состава.\n\n"
            f"3) <@&{ASSIGNABLE_ROLES['discord_admin']}> - занимается Discord сервером, а именно: кастомизация, Discord-модерация, заявки, Web-Hooks.\n"
            "<@709294538186948638>;\n\n" 
            f"4) <@&{ASSIGNABLE_ROLES['artist']}> - занимается созданием оформления всех частей Litex (Discord + Minecraft);\n\n"
            f"5) <@&{ASSIGNABLE_ROLES['texture_packer']}> - занимается созданием текстур-паков для сервера в Minecraft;\n\n"
            f"6) <@&{ASSIGNABLE_ROLES['builder']}> - официальные строители сервера. Занимаются застройкой приватных зон;\n\n"
            f"7) <@&{ASSIGNABLE_ROLES['moderator']}> - следят за порядком на сервере;\n\n"
            f"8) <@&{ASSIGNABLE_ROLES['helper']}> - помогают игрокам;\n\n"
            f"9) <@&{ASSIGNABLE_ROLES['intern']}> - стажируются в команду."
        )
        embed.description = description
        embed.set_footer(text="Это первоначальный вид данного списка (Система управления персоналом)")

        await interaction.channel.send(embed=embed, view=StaffActionView())
        await interaction.response.send_message("✅ Панель управления командой успешно создана!", ephemeral=True)

    @app_commands.command(name="staff_list", description="Показать актуальный список команды Litex")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def staff_list(self, interaction: discord.Interaction):
        if not any(role.id in STAFF_MANAGERS for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав для использования этой команды!", ephemeral=True)
            return

        guild = interaction.guild
        if not guild:
            return

        # Иерархия ролей
        ROLE_ORDER = [
            "tech_admin", "curator", "discord_admin", "artist", "texture_packer", 
            "builder", "moderator", "helper", "intern"
        ]
        
        # Строго прописанные чистые названия
        ROLE_DATA = {
            "tech_admin": {"emoji": "⚙️", "clean_name": "Технический отдел"},
            "curator": {"emoji": "🟤", "clean_name": "Куратор состава"},
            "discord_admin": {"emoji": "🛡️", "clean_name": "Дискорд-админ"},
            "artist": {"emoji": "🎨", "clean_name": "Художник"},
            "texture_packer": {"emoji": "🖌️", "clean_name": "Текстур-пакер"},
            "builder": {"emoji": "🧱", "clean_name": "Билдер"},
            "moderator": {"emoji": "🔨", "clean_name": "Модератор"},
            "helper": {"emoji": "🔰", "clean_name": "Хелпер"},
            "intern": {"emoji": "🎓", "clean_name": "Практикант"}
        }

        # 1. Собираем всех уникальных стафферов
        all_staff = set()
        for role_id in ASSIGNABLE_ROLES.values():
            role = guild.get_role(role_id)
            if role:
                all_staff.update(role.members)

        # 2. Распределяем стафферов по их ВЫСШЕЙ роли
        staff_groups = {key: [] for key in ROLE_ORDER}

        for member in all_staff:
            member_role_keys = []
            
            for key in ROLE_ORDER:
                role = guild.get_role(ASSIGNABLE_ROLES[key])
                if role and role in member.roles:
                    member_role_keys.append(key)
            
            if not member_role_keys:
                continue
                
            highest_role = member_role_keys[0]
            
            # Не добавляем основателя в тех. отдел, он пойдет в отдельное поле сверху
            if highest_role == "tech_admin" and member.id == 393700489881190411:
                continue
                
            staff_groups[highest_role].append(member.mention)

        # Вспомогательная функция для ручного внедрения конкретных пользователей
        def add_manual_user(role_key, user_id):
            mention = f"<@{user_id}>"
            if not any(mention in s for s in staff_groups[role_key]):
                staff_groups[role_key].append(mention)

        # Принудительно добавляем запрошенных людей в списки
        add_manual_user("tech_admin", 1050776902127849592)
        add_manual_user("tech_admin", 1357736754966429786)
        add_manual_user("curator", 760517178100940831)
        add_manual_user("discord_admin", 852474432232357888)

        # Принудительно удаляем основателя из тех отдела (на случай если add_manual_user или другие логики его добавят)
        staff_groups["tech_admin"] = [m for m in staff_groups["tech_admin"] if "<@393700489881190411>" not in m]

        embed = discord.Embed(
            title="✨ Актуальный состав команды Litex",
            description="Ниже представлен текущий список администрации, разработчиков и сотрудников сервера:",
            color=COLOR_EMBED
        )

        # Добавляем Основателя на самый верх
        embed.add_field(name="⚪ ・ Основатель проекта", value="<@393700489881190411>", inline=False)

        # 3. Выводим остальные категории
        for key in ROLE_ORDER:
            clean_name = ROLE_DATA[key]["clean_name"]
            emoji = ROLE_DATA[key]["emoji"]
            
            members_list = staff_groups[key]
            
            # Собираем строку участников
            value_str = ", ".join(members_list) if members_list else ""
            
            # Добавляем инфо только для дискорд-админа
            if key == "discord_admin":
                if value_str:
                    value_str += "\n<@709294538186948638>"
                else:
                    value_str = "<@709294538186948638>"
                    
            # Если в итоге строка не пустая — выводим категорию
            if value_str:
                embed.add_field(name=f"{emoji} ・ {clean_name}", value=value_str, inline=False)

        embed.set_footer(text="Litex Staff Directory • Данные обновляются в реальном времени")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    bot.add_view(StaffActionView())
    await bot.add_cog(StaffApplyCog(bot))