import datetime
import re
import asyncio
import aiohttp
import discord
import libsql
from discord import app_commands
from discord.ext import commands
from beacon import beacon_commands, preconditions
from config import TURSO_DB_URL, TURSO_AUTH_TOKEN

PARTNER_BOT_IDS = [1411266382380924938, 786446875703377940]


class EmojiStealer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = libsql.connect(
            database=TURSO_DB_URL,
            auth_token=TURSO_AUTH_TOKEN
        )

    async def cog_load(self):
        """Async initialisation when the cog is loaded."""
        def _init_db():
            cursor = self.db.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_tracker (
                    guild_id INTEGER PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL
                );
                """
            )
            self.db.commit()

        await asyncio.to_thread(_init_db)

    async def _get_guild_usage(self, guild_id: int) -> int:
        """Retrieves and manages daily usage for a guild from Turso DB."""
        today_str = datetime.date.today().isoformat()

        def _fetch():
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT count, last_updated FROM usage_tracker WHERE guild_id = ?",
                (guild_id,)
            )
            return cursor.fetchone()

        row = await asyncio.to_thread(_fetch)

        if not row:
            return 0

        count, last_updated = row
        if last_updated != today_str:
            return 0

        return count

    async def _increment_guild_usage(self, guild_id: int):
        """Increments daily steal count for a guild in Turso DB and syncs."""
        today_str = datetime.date.today().isoformat()

        def _update():
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT count, last_updated FROM usage_tracker WHERE guild_id = ?",
                (guild_id,)
            )
            row = cursor.fetchone()

            if not row or row[1] != today_str:
                cursor.execute(
                    """
                    INSERT INTO usage_tracker (guild_id, count, last_updated)
                    VALUES (?, 1, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        count = 1,
                        last_updated = excluded.last_updated
                    """,
                    (guild_id, today_str),
                )
            else:
                cursor.execute(
                    "UPDATE usage_tracker SET count = count + 1 WHERE guild_id = ?",
                    (guild_id,),
                )
            self.db.commit()

        await asyncio.to_thread(_update)


    async def _get_guild_steal_limit(self, guild: discord.Guild) -> float:
        """Determines steal quota based on how many partner bots are present in the server."""
        bots_present = 0

        for bot_id in PARTNER_BOT_IDS:
            if guild.get_member(bot_id) is not None:
                bots_present += 1
            else:
                try:
                    await guild.fetch_member(bot_id)
                    bots_present += 1
                except (discord.NotFound, discord.HTTPException):
                    pass

        if bots_present == 0:
            return 5
        elif bots_present == 1:
            return 10
        else:
            return float("inf")

    @beacon_commands.command(
        name="steal",
        description="Steal a custom emoji from any server on Discord.",
    )
    @app_commands.describe(
        emoji="Emoji or a raw Emoji ID",
        name="Optional custom name for the stolen emoji",
    )
    @preconditions.has_permissions(manage_emojis_and_stickers=True)
    async def steal(
            self,
            interaction: discord.Interaction,
            emoji: str,
            name: str | None = None,
    ):
        await interaction.response.defer(thinking=True)

        limit = await self._get_guild_steal_limit(interaction.guild)
        current_usage = await self._get_guild_usage(interaction.guild.id)

        if current_usage >= limit:
            limit_display = "5" if limit == 5 else "10"
            view = discord.ui.LayoutView()
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(f"## This server has reached the free limit of **{limit_display}** steals per day."))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(
                "**Steal-a-moji** is developed by **Dopamine Studios** as a non-profit project. To continue supporting us, our work, and to increase your limit, check out the plans below."))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("### ️:white_circle: Steal-a-moji Plus"))
            container.add_item(discord.ui.TextDisplay(
                "**Benefits:**\n* **Doubled** usage limit (10 instead of 5).\n* Fewer advertisements.\nActivate by inviting **one** of the bots below."))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("### :yellow_circle: Steal-a-moji Unlimited"))
            container.add_item(discord.ui.TextDisplay(
                "**Benefits:**\n* Everything in plus.\n* **Unlimited** usage. Steal as many emojis as you want!\n* No advertisements.\nActivate by inviting **all** of the bots below. Please note that if more bots are added to the list in the future, you will automatically be downgraded to Plus and will have to invite the new bot(s) to get back Unlimited."))
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("### The Bots"))
            dopamine_btn = discord.ui.Button(label="Invite Dopamine", style=discord.ButtonStyle.link,
                                             url="https://bot.dopaminestudios.in/invite")
            twilight_btn = discord.ui.Button(label="Invite Twilight", style=discord.ButtonStyle.link,
                                             url="https://twilight.dopaminestudios.in/invite")
            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                "* **Dopamine:** Advanced case-based, customisable moderation, giveaways, DiscordPhone, and other utilities including AFK, Sticky Messages, Autoresponse, Embed Creation, Haiku Detection, and more."),
                                                  accessory=dopamine_btn))
            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                "* **Twilight:** A privacy focused AI chatbot that does not store any user chat history."),
                                                  accessory=twilight_btn))
            view.add_item(container)
            await interaction.followup.send(view=view)
            return

        partial_emoji = None
        emoji_id = None
        emoji_name = name

        try:
            partial_emoji = discord.PartialEmoji.from_str(emoji)
            if partial_emoji and partial_emoji.is_custom_emoji():
                emoji_id = partial_emoji.id
                if not emoji_name:
                    emoji_name = partial_emoji.name
        except Exception:
            pass

        if not emoji_id:
            cleaned_input = emoji.strip()
            if cleaned_input.isdigit():
                emoji_id = int(cleaned_input)
                if not emoji_name:
                    emoji_name = f"stolen_emoji_{emoji_id}"
            else:
                await interaction.followup.send(
                    "Invalid input. Please provide either a valid custom emoji or a numerical emoji ID."
                )
                return

        emoji_name = re.sub(r"[^a-zA-Z0-9_]", "", emoji_name)[:32]
        if len(emoji_name) < 2:
            emoji_name = f"emoji_{emoji_id}"

        urls_to_try = []
        if partial_emoji:
            urls_to_try.append(str(partial_emoji.url))
        else:
            urls_to_try = [
                f"https://cdn.discordapp.com/emojis/{emoji_id}.gif",
                f"https://cdn.discordapp.com/emojis/{emoji_id}.png",
            ]

        image_bytes = None
        async with aiohttp.ClientSession() as session:
            for url in urls_to_try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        break

        if not image_bytes:
            await interaction.followup.send(
                "Could not download the emoji image. Please verify the Emoji ID is valid."
            )
            return

        try:
            new_emoji = await interaction.guild.create_custom_emoji(
                name=emoji_name,
                image=image_bytes,
                reason=f"Stolen by {interaction.user.display_name} (ID: {interaction.user.id}) via /steal",
            )

            await self._increment_guild_usage(interaction.guild.id)

            if limit == float("inf"):
                remaining_str = ""
            elif limit - (current_usage + 1) <= 3:
                remaining_str = f"-# {limit - (current_usage + 1)} more steals left today. To increase the limit for this server for free, use </upgrade:1537869677408288842>"
            else:
                remaining_str = ""
            view = discord.ui.LayoutView()
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay("## <:robber:1537842844340064287> Emoji Heist Successful"))
            container.add_item(discord.ui.TextDisplay(f"Successfully stolen {new_emoji} as `:{new_emoji.name}:`.\n{remaining_str}"))
            view.add_item(container)
            await interaction.followup.send(
                view=view
            )

        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Failed to add emoji to server: `{e.text}`"
            )

    @beacon_commands.command(
        name="upgrade", description="Upgrade your daily limit for steals"
    )
    async def upgrade(self, interaction: discord.Interaction):
        view = discord.ui.LayoutView()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## How to Upgrade"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("**Steal-a-moji** is developed by **Dopamine Studios** as a non-profit project. To continue supporting us, our work, and to increase your limit, check out the plans below."))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### ️:white_circle: Steal-a-moji Plus"))
        container.add_item(discord.ui.TextDisplay("**Benefits:**\n* **Doubled** usage limit (10 instead of 5).\n* Fewer advertisements (~16.42% -> 5% chance).\nActivate by inviting **one** of the bots below."))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### :yellow_circle: Steal-a-moji Unlimited"))
        container.add_item(discord.ui.TextDisplay("**Benefits:**\n* Everything in plus.\n* **Unlimited** usage. Steal as many emojis as you want!\n* **ZERO** advertisements.\nActivate by inviting **all** of the bots below. Please note that if more bots are added to the list in the future, you will automatically be downgraded to Plus and will have to invite the new bot(s) to get back Unlimited."))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### The Bots"))
        dopamine_btn = discord.ui.Button(label="Invite Dopamine", style=discord.ButtonStyle.link, url="https://bot.dopaminestudios.in/invite")
        twilight_btn = discord.ui.Button(label="Invite Twilight", style=discord.ButtonStyle.link, url="https://twilight.dopaminestudios.in/invite")
        container.add_item(discord.ui.Section(discord.ui.TextDisplay("* **Dopamine:** Advanced case-based, customisable moderation, giveaways, DiscordPhone, and other utilities including AFK, Sticky Messages, Autoresponse, Embed Creation, Haiku Detection, and more."), accessory=dopamine_btn))
        container.add_item(discord.ui.Section(discord.ui.TextDisplay("* **Twilight:** A privacy focused AI chatbot that does not store any user chat history."), accessory=twilight_btn))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### Your Current Plan"))
        limit = await self._get_guild_steal_limit(interaction.guild)
        if limit == float("inf"):
            line = "Your current plan is **Steal-a-moji Unlimited.** You're enjoying the best experience!"
        elif limit == 10:
            remaining = await self._get_guild_usage(interaction.guild.id)
            usage = limit - remaining
            line = f"Your current plan is **Steal-a-moji Plus.** Your remaining usage is {usage}. Upgrade to Unlimited for a limitless experience!"
        else:
            remaining = await self._get_guild_usage(interaction.guild.id)
            usage = limit - remaining
            line = f"You're currently using the default plan. Your remaining usage is {usage}. Upgrade to Plus or Unlimited for a better experience!"
        container.add_item(discord.ui.TextDisplay(line))
        view.add_item(container)
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiStealer(bot))