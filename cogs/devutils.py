import discord
from beacon import beacon_commands, ViewPaginator
from discord.ext import commands

class DevUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @beacon_commands.command(name="ls", description=".", permissions_preset="bot_owner")
    async def listservers(self, interaction: discord.Interaction):
        guilds = self.bot.guilds
        if not guilds:
            await interaction.response.send_message("I am not in any servers!", ephemeral=True)
            return

        data = [
            f"**{guild.name}** (ID: `{guild.id}`) - {guild.member_count} members"
            for guild in guilds
        ]

        view = ViewPaginator(
            user=interaction.user,
            title=f"Server List ({len(guilds)} total)",
            data=data,
            per_page=10,
            colour=discord.Colour(0xf7c22b)
        )

        await interaction.response.send_message(
            embed=view.format_embed(),
            view=view,
            ephemeral=True
        )
async def setup(bot):
    await bot.add_cog(DevUtils(bot))