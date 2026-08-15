import asyncio
import random
import time
import discord
from discord.ext import commands
from beacon import beacon_commands

ADVERTISEMENTS = [
    {
        "author": "Dopamine Studios",
        "name": "Dopamine",
        "description": "**Case-based moderation**, giveaways, DiscordPhone, utilities, and more. Click the button below to learn more.",
        "short_hook": "The Premium Experience, Minus the Paywalls",
        "link": "https://bot.dopaminestudios.in/",
        "button_label": "Learn more about Dopamine",
    },
    {
        "author": "Dopamine Studios",
        "name": "Twilight",
        "description": "Chat, ask questions, and run AI prompts directly inside your channels without leaving Discord. Click the button below to invite Twilight today.",
        "short_hook": "Privacy-focused AI chatbot",
        "link": "https://twilight.dopaminestudios.in/invite",
        "button_label": "Invite Twilight",
    },
{
        "author": "Viby Development Team",
        "name": "Viby",
        "description": "384kbps HiFi audio, a full web dashboard, smart playlists, and 24/7 auto-radio. Free forever.",
        "short_hook": "Press play, vibe on",
        "link": "https://viby.bot/",
        "button_label": "Viby's Website",
    },
]

PARTNER_BOT_IDS = {1411266382380924938, 786446875703377940}
COOLDOWN_SECONDS = 300

PLAN_ODDS = {
    "free": 69 / 420,
    "plus": 21 / 420,
}


class AdvertisementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_cooldowns: dict[int, float] = {}

    async def _get_partner_bots_count(self, guild: discord.Guild) -> int:
        """Counts cached partner bots without making slow REST API calls."""
        count = 0
        for bot_id in PARTNER_BOT_IDS:
            bot = guild.get_member(bot_id) or await guild.fetch_member(bot_id)
            if bot:
                count += 1
        return count

    def _clean_stale_cooldowns(self, now: float):
        """Prevents memory leak by pruning old guild timestamps."""
        self.guild_cooldowns = {
            g_id: ts for g_id, ts in self.guild_cooldowns.items()
            if now - ts < COOLDOWN_SECONDS
        }

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Listens only for application command interactions in guilds."""
        if not interaction.guild or interaction.type != discord.InteractionType.application_command:
            return

        asyncio.create_task(self._handle_ad_delivery(interaction))

    async def _handle_ad_delivery(self, interaction: discord.Interaction, test: bool = False):
        if not test:
            await asyncio.sleep(5)

            if not interaction.response.is_done():
                return

        guild_id = interaction.guild.id
        now = time.time()

        if not test:
            if guild_id in self.guild_cooldowns and (now - self.guild_cooldowns[guild_id] < COOLDOWN_SECONDS):
                return

            partner_count = await self._get_partner_bots_count(interaction.guild)

            if partner_count >= len(PARTNER_BOT_IDS):
                return

            chance = PLAN_ODDS["plus"] if partner_count == 1 else PLAN_ODDS["free"]

            if random.random() > chance:
                return

            self._clean_stale_cooldowns(now)
            self.guild_cooldowns[guild_id] = now

        ad_data = random.choice(ADVERTISEMENTS)
        bot_name = self.bot.user.display_name if self.bot.user else "this bot"

        view = discord.ui.LayoutView()
        container = discord.ui.Container()

        container.add_item(discord.ui.TextDisplay(f"### Enjoying {bot_name}? You might also like:"))
        container.add_item(discord.ui.TextDisplay(f"## ⭐️ {ad_data['name']} - {ad_data['short_hook']}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(ad_data["description"]))

        btn = discord.ui.Button(
            label=ad_data["button_label"],
            style=discord.ButtonStyle.link,
            url=ad_data["link"],
        )
        row = discord.ui.ActionRow()
        row.add_item(btn)

        container.add_item(row)
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# *Promoted by {ad_data["author"]} • Use </upgrade:1537869677408288842> to remove adverts for free*"))
        view.add_item(container)

        try:
            if not test:
                await interaction.followup.send(view=view, ephemeral=True)
            else:
                await interaction.response.send_message(view=view, ephemeral=True)
        except (discord.HTTPException, discord.NotFound):
            pass

    @beacon_commands.command(name="ta", description=".", permissions_preset="bot_owner")
    async def testadd(self, interaction: discord.Interaction):
        asyncio.create_task(self._handle_ad_delivery(interaction, test=True))


async def setup(bot: commands.Bot):
    await bot.add_cog(AdvertisementCog(bot))