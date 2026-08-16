import discord
from discord.ext import tasks, commands


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.change_status.start()

    def cog_unload(self):
        self.change_status.cancel()

    @tasks.loop(minutes=1)
    async def change_status(self):
        activity_name = f"😝 /steal | {len(self.bot.guilds)} Servers"

        await self.bot.change_presence(
            activity=discord.CustomActivity(name=activity_name)
        )

    @change_status.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(StatusCog(bot))