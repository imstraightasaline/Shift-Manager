import discord
import logging
import os
import json
import datetime
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands

total_times = dict({})
start_times = dict({})

with open("total_times.json", "r", encoding = "utf-8") as f: total_times = json.load(open("total_times.json"))
with open("start_times.json", "r", encoding = "utf-8") as f: start_times = json.load(open("start_times.json"))

class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

        try:
            guild = discord.Object(id=1238093282852999229)
            synced = await self.tree.sync(guild = guild)
            print(f"Synced {len(synced)} commands to guild {guild.id}")

        except Exception as err:
            print(f"Error syncing commands: {err}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        await message.reply(f"{message.content}")

handler = logging.FileHandler(filename = "bot.log", encoding = "utf-8", mode = "w")
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True
intents.dm_reactions = True
client = Client(command_prefix = "p!", intents = intents)

GUILD = discord.Object(id = 1238093282852999229)

shift_group = app_commands.Group(name = "shift", description = "Shift system")

@shift_group.command(name = "start", description = "Set your status to currently moderating")
async def start(interaction: discord.Interaction):
    mod = interaction.user.id
    if str(mod) in start_times:
        return await interaction.response.send_message(f"You already started a shift <t:{round(start_times[str(mod)])}:R> ago!")
    now = datetime.datetime.now().timestamp()
    start_times[str(mod)] = now
    with open("start_times.json", "w", encoding = "utf-8") as f: json.dump(start_times, f, ensure_ascii = False, indent = 4)
    await interaction.response.send_message("Started, check your DMs!")
    startedEmbed = discord.Embed(
        title = "Shift started!",
        description = "You have started a shift in Sining Gang, meaning that you are now actively moderating the server, and your status will be updated for all members to see. This bot will periodically be DMing you to check if you're still active, so please read the instructions once it does.\n\nTo end your shift, run `/shift_end`.",
        color = discord.Color.blurple()
    )
    startedEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")
    await interaction.user.send(embed = startedEmbed)

@shift_group.command(name = "end", description = "Ends your current moderating status")
async def end(interaction: discord.Interaction):
    mod = interaction.user.id
    if not str(mod) in start_times:
        return await interaction.response.send_message(f"You have not started a shift!")
    else:
        start = start_times[str(mod)]
        start_times.pop(str(mod), None)
        with open("start_times.json", "w", encoding = "utf-8") as f: json.dump(start_times, f, ensure_ascii = False, indent = 4)
        end = datetime.datetime.now().timestamp()
        length = (end - start)
        length_hours = length/3600
        if str(mod) in total_times:
            total_times[str(mod)] += length
        else:
            total_times[str(mod)] = length
        with open("total_times.json", "w", encoding = "utf-8") as f: json.dump(total_times, f, ensure_ascii = False, indent = 4)
        await interaction.response.send_message(f"Shift ended. Your shift lasted `{round(length_hours, 1)}` hours!")


@shift_group.command(name = "pause", description = "Pauses your shift, automatically stops it after 90 minutes")
async def pause(interaction: discord.Interaction):
    await interaction.response.send_message("paused")

@shift_group.command(name = "continue", description = "Continues your shift if it is paused")
async def cont(interaction: discord.Interaction):
    await interaction.response.send_message("continued")

client.tree.add_command(shift_group, guild = GUILD)

help_group = app_commands.Group(name = "help", description = "Information on the bot and its commands")

@app_commands.command(name = "help")
async def help(interaction: discord.Interaction):
    helpEmbed = discord.Embed(
        title = "Help",
        description = "Run `/help [category]` to get more detailed information about each category!\nThe bot exists for the Sining Gang moderation team to better support each other and its members, allowing us to share information about our current availability and remind ourselves about it with a few useful commands!\nCreated and managed by <@1238007355363299329>! Please ping/DM for any concerns.",
        color = discord.Color.blurple()
    )
    helpEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")
    helpEmbed.add_field(name = "Shift System", value = "`/shift start` - Starts a new shift\n`/shift pause` - Pauses your current shift\n`/shift continue` - Unpauses your current shift\n`/shift end` - Ends your current shift")
    helpEmbed.add_field(name = "Active Hours", value = "`/active set` - Sets the days and hours when you're available to actively moderate the server\n`/active view` - Displays in chat when your active hours are")
    helpEmbed.add_field(name = "On-Duty Display", value = "A message that displays to all members of the server who is currently on shift and people in their active hours.")
    await interaction.response.send_message(embed = helpEmbed)

@help_group.command(name = "shift", description = "Shift System detailed information")
async def shift(interaction: discord.Interaction):
    shiftEmbed = discord.Embed(
        title = "Help - Shift System",
        description = "The Shift System exists to verify that a moderator is actively monitoring the server. All shift hours are logged.\nThe idea originates from another server <@1238007355363299329> used to moderate.",
        color = discord.Color.blue()
    )
    shiftEmbed.add_field(
        name = "`/shift start`",
        value = "This starts a shift, and it has an optional parameter if you would like to specify that your DMs are open (by default they won't be). The bot will reply and send you a DM explaining that you started a shift. You are meant to actively moderate the server during a shift, not every single message and noise, but checking in every once in a while in order to make sure everything's in order. During the shift, the bot will DM you to ensure you're still active. You will have to react to this DM otherwise your shift will be paused, along with its timer of course (more information on paused shifts later). Starting a shift also starts a timer which counts how long your shift lasts.",
        inline = False
    )
    shiftEmbed.add_field(
        name = "`/shift pause`",
        value = "You can use this to manually pause a shift, for example if you need to take a break for a while. Paused shifts will automatically end after an hour.",
        inline = False
    )
    shiftEmbed.add_field(
        name = "`/shift continue`",
        value = "Used to unpause your shifts.",
        inline = False
    )
    shiftEmbed.add_field(
        name = "`/shift end`",
        value = "This ends your current shift and displays how long it lasted.",
        inline = False
    )
    await interaction.response.send_message(embed = shiftEmbed)

@help_group.command(name = "active_hours", description = "Active Hours detailed information")
async def active(interaction: discord.Interaction):
    activeEmbed = discord.Embed(
        title = "Help - Active Hours",
        description = "Moderators can use this to set what days and which specific hours on those days they're active. The bot will then remind them in the server by pinging when their active hours start.",
        color = discord.Color.blue()
    )
    activeEmbed.add_field(
        name = "`/active set`",
        value = "Use this command to set which days and hours you're available to actively moderate the server. It will ask for your timezone and active times through dropdown menus.",
        inline = False
    )
    activeEmbed.add_field(
        name = "`/active view`",
        value = "Display publicly in chat the active hours you've set.",
        inline = False
    )
    activeEmbed.add_field(
        name = "`/active disable`",
        value = "Disable your current active hours, if ever you're going to be busy for a while.",
        inline = False
    )
    activeEmbed.add_field(
        name = "`/active enable`",
        value = "Revert the previous change.",
        inline = False
        )
    await interaction.response.send_message(embed = activeEmbed)

@help_group.command(name = "on-duty_display", description = "On-Duty Display detailed information")
async def onduty(interaction: discord.Interaction):
    ondutyEmbed = discord.Embed(
        title = "Help - On-Duty Display",
        description = "A message that displays which people are currently in a shift, and which people are currently in their active hours. It recommends server members to ping any on-duty moderators for assistance, and if there are currently none available, it recommends the ones in their available hours instead. It also displays if those on-duty accept DMs. This message is automatically updated by the bot. See a preview of what it looks like below.\n\nThis message can only be configured by managers of the bot (<@1238007355363299329>, <@442961966596751371>).",
        color = discord.Color.blue()
    )
    ondutyEmbed.add_field(
        name = "Available Moderators",
        value = "The following moderators are currently available! You are free to ping the ones **On-Duty** if you have any concerns that need immediate attention. If there are currently no mods on-duty, please notify an online mod under **Available**.\n\n**On-Duty:**\n<@476673046313435158>\n<@1238007355363299329> - DMs open!\n\n**Available:**\n<@442961966596751371>",
        inline = False
    )
    await interaction.response.send_message(embed = ondutyEmbed)

client.tree.add_command(help_group, guild = GUILD)

async def check_status():
    await client.wait_until_ready()
    while not client.is_closed:
        return

load_dotenv()
# dict = {"key":"value"}
# with open("test.json", "w", encoding = "utf-8") as f: json.dump(dict, f, ensure_ascii = False, indent = 4)
# with open("test.json", "r", encoding = "utf-8") as f: new = json.load(open("test.json"))
# new["test"] = "testing"
# with open("test.json", "w", encoding = "utf-8") as f: json.dump(new, f, ensure_ascii = False, indent = 4)
# dict.pop("key", None)
client.run(os.getenv("TOKEN"), log_handler = handler, log_level = logging.DEBUG)