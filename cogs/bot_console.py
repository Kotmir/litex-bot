import sys
import logging
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import config

DB_PATH = getattr(config, "DB_PATH", "litex.db")
EMBED_COLOR = discord.Color.from_rgb(186, 85, 211)

class ConsoleStreamRedirector:
    """Перехватывает всё, что пишется в консоль, и отправляет в Discord"""
    def __init__(self, bot: commands.Bot, original_stream):
        self.bot = bot
        self.original_stream = original_stream

    def write(self, message):
        self.original_stream.write(message)
        self.original_stream.flush()
        
        cleaned = message.strip()
        if cleaned:
            self.bot.loop.create_task(self.send_to_discord(cleaned))

    def flush(self):
        self.original_stream.flush()

    async def send_to_discord(self, message: str):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT console_channel_id FROM console_settings LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return
                    channel_id = row[0]

            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                if len(message) > 1900:
                    message = message[:1900] + "..."
                await channel.send(f"```ini\n{message}\n```")
        except Exception:
            pass


class BotConsole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not isinstance(sys.stdout, ConsoleStreamRedirector):
            sys.stdout = ConsoleStreamRedirector(bot, sys.stdout)

    @commands.Cog.listener()
    async def on_ready(self):
        """Отправляет красивый отчет о запуске в канал консоли при старте бота"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT console_channel_id FROM console_settings LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return
                    channel_id = row[0]

            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="🚀 Бот успешно запущен и готов к работе!",
                    description=(
                        f"🤖 **Имя бота:** `{self.bot.user}`\n"
                        f"🆔 **ID бота:** `{self.bot.user.id}`\n"
                        f"🌐 **Серверов в сети:** `{len(self.bot.guilds)}`\n"
                        f"📦 **Загружено когов:** `{len(self.bot.cogs)}`"
                    ),
                    color=EMBED_COLOR,
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text="Проект Litex • Системный запуск")
                await channel.send(embed=embed)
        except Exception:
            pass

    @app_commands.command(
        name="set_console_channel",
        description="Установить текущий канал в качестве консоли логов бота (Только для Администрации)"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_console_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS console_settings (
                    guild_id INTEGER PRIMARY KEY,
                    console_channel_id INTEGER
                )"""
            )
            await db.execute(
                """INSERT INTO console_settings (guild_id, console_channel_id) 
                   VALUES (?, ?) 
                   ON CONFLICT(guild_id) DO UPDATE SET console_channel_id = ?""",
                (interaction.guild.id, interaction.channel.id, interaction.channel.id)
            )
            await db.commit()

        embed = discord.Embed(
            title="🖥️ Консоль логов успешно подключена",
            description=f"Теперь вся консольная информация будет дублироваться в этот канал ({interaction.channel.mention}).",
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Проект Litex • Системный мониторинг")

        await interaction.channel.send(embed=embed)
        await interaction.followup.send(
            f"✅ Канал {interaction.channel.mention} назначен консолью логов!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BotConsole(bot))
