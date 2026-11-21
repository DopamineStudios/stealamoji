import asyncio
import random
import re
import traceback
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from beacon import beacon_commands, preconditions


class EmojiStealer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji_index: dict[int, dict] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        self.rebuild_index()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.add_guild_to_index(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        self.remove_guild_from_index(guild.id)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ):
        self.remove_guild_from_index(guild.id)
        self.add_guild_to_index(guild)

    def rebuild_index(self):
        self.emoji_index.clear()
        for guild in self.bot.guilds:
            self.add_guild_to_index(guild)

    def add_guild_to_index(self, guild: discord.Guild):
        for emoji in guild.emojis:
            self.emoji_index[emoji.id] = {
                "id": emoji.id,
                "name": emoji.name,
                "animated": emoji.animated,
                "guild_id": guild.id,
                "guild_name": guild.name,
                "string_repr": str(emoji),
                "search_key": emoji.name.lower(),
            }

    def remove_guild_from_index(self, guild_id: int):
        to_remove = [
            eid
            for eid, data in self.emoji_index.items()
            if data["guild_id"] == guild_id
        ]
        for eid in to_remove:
            del self.emoji_index[eid]

    async def emoji_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        current = current.strip().lower()
        choices = []
        for emoji_info in self.emoji_index.values():
            if (
                not current
                or current in emoji_info["search_key"]
                or current in str(emoji_info["id"])
            ):
                display_name = f":{emoji_info['name']}: ({emoji_info['guild_name']})"[
                    :100
                ]
                choices.append(
                    app_commands.Choice(
                        name=display_name, value=emoji_info["string_repr"]
                    )
                )
                if len(choices) >= 25:
                    break
        return choices

    @beacon_commands.command(
        name="steal",
        description="Steal a custom emoji from any server on Discord.",
    )
    @app_commands.describe(
        emoji="Emoji or a raw Emoji ID",
        name="Optional custom name for the stolen emoji",
    )
    @app_commands.autocomplete(emoji=emoji_autocomplete)
    @preconditions.has_permissions(manage_emojis_and_stickers=True)
    async def steal(
            self,
            interaction: discord.Interaction,
            emoji: str,
            name: str | None = None,
    ):
        try:
            await interaction.response.defer(thinking=True)

            partial_emoji = None
            emoji_id = None
            emoji_name = name
            cleaned_input = emoji.strip()
            direct_urls = []
            is_animated = False

            try:
                parsed = discord.PartialEmoji.from_str(emoji)
                if parsed and parsed.is_custom_emoji():
                    partial_emoji = parsed
                    emoji_id = partial_emoji.id
                    is_animated = partial_emoji.animated
                    if not emoji_name:
                        emoji_name = partial_emoji.name or f"stealamoji_{emoji_id}"
            except Exception:
                pass

            if not emoji_id and cleaned_input.isdigit():
                emoji_id = int(cleaned_input)
                if not emoji_name:
                    emoji_name = f"stealamoji_{emoji_id}"

            if not emoji_id and cleaned_input.lower().startswith(("http://", "https://")):
                direct_urls.append(cleaned_input)
                match = re.search(r"/emojis/(\d+)\.(png|gif|webp|jpeg)", cleaned_input, re.IGNORECASE)
                if match:
                    emoji_id = int(match.group(1))
                    if match.group(2).lower() == "gif":
                        is_animated = True

                if not emoji_name:
                    from urllib.parse import urlparse
                    import os
                    path = urlparse(cleaned_input).path
                    basename = os.path.basename(path)
                    name_part, _ = os.path.splitext(basename)
                    if name_part:
                        emoji_name = name_part
                    else:
                        emoji_name = f"stealamoji_{emoji_id if emoji_id else 'media'}"

            if not emoji_id and not direct_urls:
                await interaction.followup.send(
                    "Invalid input. Please provide a valid custom emoji, numerical emoji ID, Discord emoji link, or media link."
                )
                return

            emoji_name = re.sub(r"[^a-zA-Z0-9_]", "", emoji_name)[:32]
            if len(emoji_name) < 2:
                emoji_name = f"stealamoji_{emoji_id if emoji_id else 'emoji'}"

            urls_to_try = []
            if direct_urls:
                urls_to_try.extend(direct_urls)
            elif partial_emoji:
                urls_to_try.append(str(partial_emoji.url))
            elif emoji_id:
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
                        else:
                            continue

            if not image_bytes:
                await interaction.followup.send(
                    "Could not download the emoji image. Please verify the Emoji ID is valid."
                )
                return

            try:
                # Set a short timeout so the bot doesn't hang for 576 seconds waiting for discord.py's internal retry
                new_emoji = await asyncio.wait_for(
                    interaction.guild.create_custom_emoji(
                        name=emoji_name,
                        image=image_bytes,
                        reason=f"Stolen by {interaction.user.display_name} (ID: {interaction.user.id}) via /steal",
                    ),
                    timeout=5.0
                )

                view = discord.ui.LayoutView()
                container = discord.ui.Container()
                container.add_item(discord.ui.TextDisplay("## <:robber:1537842844340064287> Emoji Heist Successful"))
                container.add_item(discord.ui.TextDisplay(f"Successfully stole {new_emoji} as `:{new_emoji.name}:`"))
                invite_btn = discord.ui.Button(label="Invite", style=discord.ButtonStyle.link,
                                               url="https://stealamoji.dopaminestudios.in/invite")
                website_btn = discord.ui.Button(label="Website", style=discord.ButtonStyle.link,
                                                url="https://stealamoji.dopaminestudios.in/")
                num = random.randint(1, 3)
                if num == 2:
                    row = discord.ui.ActionRow()
                    row.add_item(invite_btn)
                    container.add_item(row)
                elif num == 3:
                    row = discord.ui.ActionRow()
                    row.add_item(website_btn)
                    container.add_item(row)

                view.add_item(container)
                await interaction.followup.send(view=view)

            except asyncio.TimeoutError:
                await interaction.followup.send(
                    f"⚠️ **Rate Limit Exceeded:** Discord is currently rate-limiting emoji additions for this server. This rate limit applies to all bots and users in the server, not just Steal a 'Moji. Please try again later."
                )

            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = getattr(e, "retry_after", 0)
                    minutes = int(retry_after // 60)
                    seconds = int(retry_after % 60)
                    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                    await interaction.followup.send(
                        f"⚠️ **Rate Limit Exceeded:** Discord is rate-limiting emoji additions for this server.\n"
                        f"Please try again in **{time_str}**."
                    )
                elif e.code == 30008:
                    is_animated = partial_emoji.animated if partial_emoji else False
                    emoji_type = "animated" if is_animated else "static"
                    await interaction.followup.send(
                        f"Failed to add emoji: This server has reached its limit for {emoji_type} emojis!"
                    )
                else:
                    await interaction.followup.send(
                        f"Failed to add emoji to server: `{e.text}`"
                    )
        except Exception as e:
            self.bot.logger.critical(f"ERROR in /steal command\n{e}\n{traceback.format_exc()}")


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiStealer(bot))