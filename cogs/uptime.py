import discord
from discord.ext import commands
from aiohttp import web
import asyncio
import os

try:
    from config import MONITOR_PORT
except ImportError:
    MONITOR_PORT = 8080

PORT = int(os.environ.get("PORT", MONITOR_PORT))


class StatusMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.port = PORT
        self.app = web.Application()

        self.app.router.add_get('/', self.handle_ping)
        self.app.router.add_get('/ping', self.handle_ping)

        self.runner = None
        self.site = None

        self.server_task = asyncio.create_task(self.start_server())

    async def handle_ping(self, request):
        """Responds to the incoming ping from BetterStack."""
        return web.Response(text="OK", status=200)

    async def start_server(self):
        """Initialises and starts the web server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)

        try:
            await self.site.start()
            if hasattr(self.bot, 'logger'):
                self.bot.logger.info(f"Monitor web server successfully started on port {self.port}")
        except Exception as e:
            if hasattr(self.bot, 'logger'):
                self.bot.logger.critical(f"Failed to start the monitor web server: {e}")

            await self.bot.wait_until_ready()
            await self.notify_owners(f"The monitor web server failed to start on port {self.port}: ```{e}```")

    async def notify_owners(self, message: str):
        """Helper to safely identify and notify bot owners if something goes wrong."""
        if not self.bot:
            return

        if self.bot.owner_ids:
            owners = list(self.bot.owner_ids)
        elif self.bot.owner_id:
            owners = [self.bot.owner_id]
        else:
            try:
                app = await self.bot.application_info()
                if app.team:
                    owners = [m.id for m in app.team.members]
                else:
                    owners = [app.owner.id]
            except Exception as e:
                if hasattr(self.bot, 'logger'):
                    self.bot.logger.error(f"Could not fetch application info for owner notification: {e}")
                return

        for owner_id in owners:
            try:
                owner = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                await owner.send(f"**Critical failure:** {message}")
            except Exception as e:
                if hasattr(self.bot, 'logger'):
                    self.bot.logger.error(f"Could not send DM to owner {owner_id}: {e}")

    def cog_unload(self):
        """Cleans up the web server resources when the cog is unloaded."""
        self.server_task.cancel()
        if self.runner:
            asyncio.create_task(self.runner.cleanup())


async def setup(bot):
    await bot.add_cog(StatusMonitor(bot))