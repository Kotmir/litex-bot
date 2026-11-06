import aiosqlite
import discord
from discord.ext import commands
from discord import app_commands
import config

EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)  # Розово-фиолетовый цвет Litex
DB_PATH = getattr(config, "DB_PATH", "litex.db")

class InviteLogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invites_cache: dict[int, dict[str, int]] = {}

    async def cog_load(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS invite_settings (
                    guild_id INTEGER PRIMARY KEY,
                    invite_channel_id INTEGER
                )"""
            )
            await db.commit()

        for guild in self.bot.guilds:
            await self.update_guild_invites(guild)

    async def update_guild_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self.invites_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except discord.Forbidden:
            self.invites_cache[guild.id] = {}

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.update_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            if invite.guild.id not in self.invites_cache:
                self.invites_cache[invite.guild.id] = {}
            self.invites_cache[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild and invite.guild.id in self.invites_cache:
            self.invites_cache[invite.guild.id].pop(invite.code, None)

    async def get_invite_channel_id(self, guild_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT invite_channel_id FROM invite_settings WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        channel_id = await self.get_invite_channel_id(guild.id)
        if not channel_id:
            return

        log_channel = guild.get_channel(channel_id)
        if not log_channel or not isinstance(log_channel, discord.TextChannel):
            return

        inviter = None
        used_invite_code = None

        try:
            old_invites = self.invites_cache.get(guild.id, {})
            new_invites = await guild.invites()
            
            for new_inv in new_invites:
                old_uses = old_invites.get(new_inv.code, 0)
                if new_inv.uses > old_uses:
                    inviter = new_inv.inviter
                    used_invite_code = new_inv.code
                    break

            self.invites_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
        except discord.Forbidden:
            pass

        if inviter:
            inviter_member = guild.get_member(inviter.id)
            display_name = inviter_member.display_name if inviter_member else inviter.name
            
            total_invites = 0
            try:
                current_invites = await guild.invites()
                for inv in current_invites:
                    if inv.inviter and inv.inviter.id == inviter.id:
                        total_invites += inv.uses
            except discord.Forbidden:
                total_invites = 1

            inviter_text = f"🎁 Пригласил: **{display_name}** (`@{inviter.name}`)\n📊 Всего приглашений: **{total_invites}**"
            footer_text = f"Проект Litex • Приглашение: {used_invite_code}" if used_invite_code else "Проект Litex • По пригласительной ссылке"
        else:
            inviter_text = "🌐 Приглашение: **Серверная ссылка / Vanity URL / Реклама**"
            footer_text = "Проект Litex • Прямое вступление"

        embed = discord.Embed(
            title=f"✨ Новый участник на сервере {guild.name}!",
            description=(
                f"👋 Пользователь {member.mention} успешно присоединился к нам!\n\n"
                f"{inviter_text}\n\n"
                f"📌 **Информация об аккаунте:**\n"
                f"> • Создан: {discord.utils.format_dt(member.created_at, style='R')}\n"
                f"> • ID: `{member.id}`"
            ),
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=footer_text,
            icon_url=guild.icon.url if guild.icon else None,
        )

        await log_channel.send(embed=embed)

    @app_commands.command(
        name="set_invite_channel",
        description="Установить текущий канал для отправки логов приглашений (Только для Администрации)"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_invite_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO invite_settings (guild_id, invite_channel_id) 
                   VALUES (?, ?) 
                   ON CONFLICT(guild_id) DO UPDATE SET invite_channel_id = ?""",
                (interaction.guild.id, interaction.channel.id, interaction.channel.id)
            )
            await db.commit()

        await interaction.followup.send(
            f"✅ Успешно! Теперь логи новых участников будут отправляться в канал {interaction.channel.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteLogs(bot))