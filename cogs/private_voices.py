import discord
from discord import app_commands
from discord.ext import commands

CREATOR_CHANNEL_ID = 1566999629403398215
COLOR_EMBED = 0xEC4899

active_private_channels = {}  # {channel_id: owner_id}


class RenameModal(discord.ui.Modal, title="Изменить название комнаты"):
    new_name = discord.ui.TextInput(
        label="Новое название",
        placeholder="Введите название для вашей комнаты...",
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не находитесь в голосовом канале!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не являетесь владельцем этой комнаты!", ephemeral=True)
            return

        await channel.edit(name=self.new_name.value)
        await interaction.response.send_message(f"✅ Название комнаты изменено на: **{self.new_name.value}**", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Лимит участников"):
    limit = discord.ui.TextInput(
        label="Количество человек (0 - без лимита)",
        placeholder="Например: 5",
        max_length=2,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не находитесь в голосовом канале!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не являетесь владельцем этой комнаты!", ephemeral=True)
            return

        try:
            val = int(self.limit.value)
            if not (0 <= val <= 99):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите число от 0 до 99.", ephemeral=True)
            return

        await channel.edit(user_limit=val)
        limit_text = "без лимита" if val == 0 else str(val)
        await interaction.response.send_message(f"✅ Лимит участников изменен: **{limit_text}**", ephemeral=True)


# --- ВЫПАДАЮЩИЕ МЕНЮ ДЛЯ УПРАВЛЕНИЯ ---

class OwnerSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="👑 Выберите нового владельца комнаты...", max_values=1, min_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        new_owner = self.values[0]
        if new_owner.bot:
            await interaction.response.send_message("❌ Нельзя передать комнату боту!", ephemeral=True)
            return
        if new_owner not in channel.members:
            await interaction.response.send_message("❌ Этот пользователь должен находиться в вашей комнате!", ephemeral=True)
            return

        active_private_channels[channel.id] = new_owner.id
        await channel.set_permissions(new_owner, manage_channels=True, connect=True, speak=True, move_members=True)
        await channel.set_permissions(interaction.user, manage_channels=False)

        await interaction.response.send_message(f"👑 Новый владелец комнаты: {new_owner.mention}!", ephemeral=True)


class KickSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="➡️ Выберите кого выгнать из комнаты...", max_values=1, min_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        target = self.values[0]
        if target not in channel.members:
            await interaction.response.send_message("❌ Пользователь не находится в вашей комнате!", ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ Нельзя выгнать самого себя!", ephemeral=True)
            return

        await target.move_to(None)
        await interaction.response.send_message(f"➡️ Пользователь {target.mention} был выгнан из комнаты.", ephemeral=True)


class MicSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="🎤 Выберите участника (мутать/размутать)...", max_values=1, min_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        target = self.values[0]
        if target not in channel.members:
            await interaction.response.send_message("❌ Пользователь не в вашей комнате!", ephemeral=True)
            return

        current_perm = channel.permissions_for(target).speak
        new_perm = not current_perm
        await channel.set_permissions(target, speak=new_perm)

        action_text = "разрешено говорить" if new_perm else "запрещено говорить"
        await interaction.response.send_message(f"🎤 Пользователю {target.mention} **{action_text}**.", ephemeral=True)


class OwnerSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(OwnerSelect())


class KickSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(KickSelect())


class MicSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(MicSelect())


# --- ОСНОВНАЯ ПАНЕЛЬ КНОПОК ---

class VoiceControlView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.secondary, custom_id="vc_owner", row=0)
    async def change_owner(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("👑 Выберите нового владельца из списка ниже:", view=OwnerSelectView(), ephemeral=True)

    @discord.ui.button(emoji="👤", style=discord.ButtonStyle.secondary, custom_id="vc_access", row=0)
    async def access_settings(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        is_private = overwrite.view_channel is False
        overwrite.view_channel = True if is_private else False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        status = "публичная (видна всем)" if is_private else "приватная (скрыта от остальных)"
        await interaction.response.send_message(f"👤 Доступ изменен: теперь комната **{status}**.", ephemeral=True)

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, custom_id="vc_limit", row=0)
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(LimitModal())

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="vc_lock", row=0)
    async def toggle_lock(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        is_locked = overwrite.connect is False
        overwrite.connect = True if is_locked else False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        status = "открыта" if is_locked else "закрыта"
        await interaction.response.send_message(f"🔒 Комната успешно **{status}** для подключения!", ephemeral=True)

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="vc_rename", row=1)
    async def rename_room(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="vc_hide", row=1)
    async def toggle_hide(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы не в голосовом канале!", ephemeral=True)
            return
        channel = interaction.user.voice.channel
        if active_private_channels.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ Вы не владелец комнаты!", ephemeral=True)
            return

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        is_hidden = overwrite.view_channel is False
        overwrite.view_channel = True if is_hidden else False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        status = "видна всем" if is_hidden else "скрыта"
        await interaction.response.send_message(f"👁️ Комната теперь **{status}**!", ephemeral=True)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="vc_kick", row=1)
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("➡️ Выберите участника, которого нужно выгнать:", view=KickSelectView(), ephemeral=True)

    @discord.ui.button(emoji="🎤", style=discord.ButtonStyle.secondary, custom_id="vc_mic", row=1)
    async def toggle_mic(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("🎙️ Выберите участника для изменения прав говорения:", view=MicSelectView(), ephemeral=True)


class PrivateVoicesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup_voice_panel",
        description="Отправить панель управления приватными комнатами"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def setup_voice_panel(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="⚙️ Приватные комнаты",
            description=(
                "Измените конфигурацию вашей комнаты с помощью панели управления.\n"
                "👑 назначить нового создателя комнаты\n"
                "👤 управление доступом к комнате\n"
                "👥 задать новый лимит участников\n"
                "🔒 закрыть/открыть комнату\n"
                "✏️ изменить название комнаты\n"
                "👁️ скрыть/открыть комнату\n"
                "➡️ выгнать участника из комнаты\n"
                "🎤 ограничить/выдать право говорить"
            ),
            color=COLOR_EMBED,
        )
        embed.set_footer(text="Litex Voice System")

        await interaction.channel.send(embed=embed, view=VoiceControlView())
        await interaction.response.send_message("✅ Панель успешно отправлена!", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        guild = member.guild

        # 1. Создание комнаты при входе в триггер
        if after.channel and after.channel.id == CREATOR_CHANNEL_ID:
            category = after.channel.category
            channel_name = f"🔊・{member.display_name}"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, connect=True, speak=True, move_members=True),
            }

            try:
                new_channel = await guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                )
                active_private_channels[new_channel.id] = member.id
                await member.move_to(new_channel)
            except Exception as e:
                pass

        # 2. Удаление пустой комнаты
        if before.channel:
            is_our_private_channel = (
                before.channel.id in active_private_channels or 
                before.channel.name.startswith("🔊・")
            )
            
            if is_our_private_channel and len(before.channel.members) == 0:
                channel_id = before.channel.id
                try:
                    await before.channel.delete(reason="Приватный канал пуст")
                except Exception as e:
                    pass
                active_private_channels.pop(channel_id, None)


async def setup(bot: commands.Bot) -> None:
    bot.add_view(VoiceControlView())
    await bot.add_cog(PrivateVoicesCog(bot))