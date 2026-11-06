import discord
from discord import app_commands
from discord.ext import commands

# ID вашего второго сервера
SECOND_GUILD_ID = 1535608768761434154
SECOND_GUILD_OBJ = discord.Object(id=SECOND_GUILD_ID)

COLOR_SECOND = 0xEC4899  # Цвет эмбедов для второго сервера


class SecondServerCog(commands.Cog):
    """Модуль команд исключительно для второго сервера."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Пример слэш-команды, которая видна ТОЛЬКО на втором сервере
    @app_commands.command(
        name="info",
        description="Информация (только для второго сервера)"
    )
    @app_commands.guilds(SECOND_GUILD_OBJ)
    async def info_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="📌 Меню второго сервера",
            description="Эта команда работает и отображается только на этом сервере!",
            color=COLOR_SECOND
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Пример обработчика событий (например, сообщения или вход участников) только для второго сервера
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        # Игнорируем всё, что происходит НЕ на втором сервере
        if message.guild.id != SECOND_GUILD_ID:
            return

        # Здесь можно писать любую логику специально для второго сервера


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SecondServerCog(bot))