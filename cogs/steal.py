import random
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from beacon import beacon_commands, preconditions
import traceback


class EmojiStealer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        try:
            await interaction.response.defer(thinking=True)

            partial_emoji = None
            emoji_id = None
            emoji_name = name

            try:
                partial_emoji = discord.PartialEmoji.from_str(emoji)
                if partial_emoji and partial_emoji.is_custom_emoji():
                    emoji_id = partial_emoji.id
                    if not emoji_name:
                        emoji_name = partial_emoji.name or f"stealamoji_{emoji_id}"
            except Exception:
                pass

            if not emoji_id:
                cleaned_input = emoji.strip()
                if cleaned_input.isdigit():
                    emoji_id = int(cleaned_input)
                    self.bot.logger.info(f"{emoji_id}")
                    if not emoji_name:
                        emoji_name = f"stealamoji_{emoji_id}"
                else:
                    await interaction.followup.send(
                        "Invalid input. Please provide either a valid custom emoji or a numerical emoji ID."
                    )
                    return

            emoji_name = re.sub(r"[^a-zA-Z0-9_]", "", emoji_name)[:32]
            if len(emoji_name) < 2:
                emoji_name = f"stealamoji_{emoji_id}"

            urls_to_try = []
            if partial_emoji:
                urls_to_try.append(str(partial_emoji.url))
            else:
                urls_to_try = [
                    f"https://cdn.discordapp.com/emojis/{str(emoji_id)}.gif",
                    f"https://cdn.discordapp.com/emojis/{str(emoji_id)}.png",
                ]

            image_bytes = None
            async with aiohttp.ClientSession() as session:
                for url in urls_to_try:
                    self.bot.logger.info(f"Trying: {url} URL")
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
                new_emoji = await interaction.guild.create_custom_emoji(
                    name=emoji_name,
                    image=image_bytes,
                    reason=f"Stolen by {interaction.user.display_name} (ID: {interaction.user.id}) via /steal",
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

            except discord.HTTPException as e:
                if e.code == 30008:
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