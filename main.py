import discord
import logging
import os
import json
import datetime
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, Button, View

data = {"total_times": dict({}), "current_times": dict({}), "active_hours": dict({})}

async def handleFile(name, method):
    if method == "read":
        with open("./data/" + name + ".json", "r", encoding = "utf-8") as f: data[name] = json.load(open("./data/" + name + ".json"))
    else:
        with open("./data/" + name + ".json", "w", encoding = "utf-8") as f: json.dump(data[name], f, ensure_ascii = False, indent = 4)

GUILD = discord.Object(id = 1238093282852999229)

class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

        status_check.start()

        try:
            await handleFile("total_times", "read")
            await handleFile("current_times", "read")
            await handleFile("active_hours", "read")
            print(f"Data read from files")
            pass
        except Exception as err:
            print(f"Error reading file data: {err}")

        try:
            synced = await self.tree.sync(guild = GUILD)
            print(f"Synced {len(synced)} commands to guild {GUILD.id}")

        except Exception as err:
            print(f"Error syncing commands: {err}")

handler = logging.FileHandler(filename = "bot.log", encoding = "utf-8", mode = "w")
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True
intents.dm_reactions = True
client = Client(command_prefix = "p!", intents = intents)

shift_group = app_commands.Group(name = "shift", description = "Shift system")

@shift_group.command(name = "start", description = "Set your status to currently moderating")
async def start(interaction: discord.Interaction, dms: bool=False):
    now = datetime.datetime.now().timestamp()
    details = {
        "start": now,
        "dms": False,
        "paused": False,
        "pauses": [],
        "status_check": {
            "msg": 0,
            "next": (now + 10) # 1800
        }
    }
    if dms:
        details["dms"] = True
    mod = str(interaction.user.id)
    if mod in data["current_times"]:
        return await interaction.response.send_message(f"Hey {interaction.user.mention}, you already started a shift <t:{round(data["current_times"][mod]["start"])}:R> ago!")
    data["current_times"][mod] = details
    await handleFile("current_times", "write")
    await interaction.response.send_message(f"Started for {interaction.user.mention}, check your DMs!")
    startedEmbed = discord.Embed(
        title = "Shift started!",
        description = f"Hi {interaction.user.nick}! You have started a shift in Sining Gang, meaning that you are now actively moderating the server, and your status will be updated for all members to see. This bot will periodically be DMing you to check if you're still active, so please read the instructions once it does.\n\nTo end your shift, run `/shift_end`.",
        color = discord.Color.blurple()
    )
    startedEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")
    await interaction.user.send(embed = startedEmbed)

async def endShift(mod): # add deduction from pauses
    end = datetime.datetime.now().timestamp()
    user = client.get_user(int(mod))
    lastCheck = data["current_times"][mod]["status_check"]["msg"]
    if lastCheck > 0:
        check = await user.fetch_message(lastCheck)
        await check.edit(content = f"<t:{round(end)}:R>\n> Status Check cancelled as the shift has ended.", embed = None, view = None)
    start = data["current_times"][mod]["start"]
    data["current_times"].pop(mod, None)
    await handleFile("current_times", "write")
    length = (end - start)
    length_hours = round(length/3600, 1)
    if mod in data["total_times"]:
        data["total_times"][mod] += length
    else:
        data["total_times"][mod] = length
    await handleFile("total_times", "write")
    return length_hours

@shift_group.command(name = "end", description = "Ends your current moderating status")
async def end(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!")
    else:
        await interaction.response.send_message(f"Shift ended. Your shift lasted `{await endShift(mod)}` hours!")


@shift_group.command(name = "pause", description = "Pauses your shift, automatically stops it after 90 minutes")
async def pause(interaction: discord.Interaction):
    now = datetime.datetime.now().timestamp()
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!")
    if data["current_times"][mod]["paused"]:
        return await interaction.response.send_message(f"Shift already paused!")
    data["current_times"][mod]["paused"] = True
    data["current_times"][mod]["pauses"].append(now)
    await handleFile("current_times", "write")
    await interaction.response.send_message("Shift paused!")

@shift_group.command(name = "continue", description = "Continues your shift if it is paused")
async def cont(interaction: discord.Interaction):
    now = datetime.datetime.now().timestamp()
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!")
    data["current_times"][mod]
    if not data["current_times"][mod]["paused"]:
        return await interaction.response.send_message(f"Shift is not paused!")
    data["current_times"][mod]["paused"] = False
    last_entry = len(data["current_times"][mod]["pauses"]) - 1
    data["current_times"][mod]["pauses"][last_entry] = (now - data["current_times"][mod]["pauses"][last_entry])
    data["current_times"][mod]["status_check"]["next"] = (now + 1800)
    await handleFile("current_times", "write")
    await interaction.response.send_message("continued")

client.tree.add_command(shift_group, guild = GUILD)

active_group = app_commands.Group(name = "active", description = "Active Hours tracker")

@active_group.command(name = "set", description = "Set your active hours")
async def set(interaction: discord.Interaction):
    return

help_group = app_commands.Group(name = "help", description = "Information on the bot and its commands")

@help_group.command(name = "general", description = "Information on the bot and its commands")
async def general(interaction: discord.Interaction):
    helpEmbed = discord.Embed(
        title = "Help",
        description = "Run `/help [category]` to get more detailed information about each category!\nThe bot exists for the Sining Gang moderation team to better support each other and its members, allowing us to share information about our current availability and remind ourselves about it with a few useful commands!",
        color = discord.Color.blurple()
    )
    helpEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")
    helpEmbed.add_field(
        name = "Shift System",
        value = "`/shift start [dms: true/false]` - Starts a new shift, DMs off by default\n`/shift pause` - Pauses your current shift\n`/shift continue` - Unpauses your current shift\n`/shift end` - Ends your current shift",
        inline = False
    )
    helpEmbed.add_field(
        name = "Active Hours",
        value = "`/active set` - Sets the days and hours when you're available to actively moderate the server\n`/active view` - Displays in chat when your active hours are\n`/active disable` - Sets all your active hours to none\n`/active enable` - Returns your saved active hours",
        inline = False
    )
    helpEmbed.add_field(
        name = "On-Duty Display",
        value = "A message that displays to all members of the server who is currently on shift and people in their active hours.",
        inline = False
    )
    helpEmbed.set_footer(text = "Created and managed by Carol! Ping/DM for any concerns.")
    await interaction.response.send_message(embed = helpEmbed)

@help_group.command(name = "shift", description = "Shift System detailed information")
async def shift(interaction: discord.Interaction):
    shiftEmbed = discord.Embed(
        title = "Help - Shift System",
        description = "The Shift System exists to verify that a moderator is actively monitoring the server. All shift hours are logged.\nThe idea originates from another server <@1238007355363299329> used to moderate.",
        color = discord.Color.blue()
    )
    shiftEmbed.add_field(
        name = "`/shift start [dms: true/false]`",
        value = "This starts a shift, and it has an optional parameter if you would like to specify that your DMs are open (they won't be if you don't specify). The bot will reply and send you a DM explaining that you started a shift. You are meant to actively moderate the server during a shift, not every single message and noise, but checking in every once in a while in order to make sure everything's in order. During the shift, the bot will DM you to ensure you're still active. You will have to react to this DM otherwise your shift will be paused, along with its timer of course (more information on paused shifts later). Starting a shift also starts a timer which counts how long your shift lasts.",
        inline = False
    )
    shiftEmbed.add_field(
        name = "`/shift pause`",
        value = "You can use this to manually pause a shift, for example if you need to take a break for a while. Paused shifts will automatically end after 90 minutes.",
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
        value = "Revert the previous change, putting back the active hours you set.",
        inline = False
    )
    await interaction.response.send_message(embed = activeEmbed)

@help_group.command(name = "onduty_display", description = "On-Duty Display detailed information")
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

@tasks.loop(minutes = 1)
async def status_check():
    tempdict = data["current_times"]
    for mod in tempdict:
        now = datetime.datetime.now().timestamp()
        user = client.get_user(int(mod))
        if not data["current_times"][mod]["paused"]:
            if now > data["current_times"][mod]["status_check"]["next"]:
                if now > (data["current_times"][mod]["status_check"]["next"] + 600): # 600
                    check = await user.fetch_message(data["current_times"][mod]["status_check"]["msg"])
                    data["current_times"][mod]["paused"] = True
                    data["current_times"][mod]["pauses"].append(now)
                    await handleFile("current_times", "write")
                    await check.edit(view = None)
                    return await user.send(f"You did not confirm your status and your shift has been paused!\nPlease unpause your shift by running `/shift continue`, else it will automatically end <t:{round(now) + 5400}:R>.")
                elif data["current_times"][mod]["status_check"]["msg"] == 0:
                    checkEmbed = discord.Embed(
                        title = "Status Check",
                        description = "Hello! If you're still here, please click the reaction down below. If you don't react within 10 minutes, your shift will be paused. Thank you!",
                        color = discord.Color.random()
                    )
                    button = Button(label = "Still here!", style = discord.ButtonStyle.primary, emoji = "<:teehee:1524809416149569588>")
                    async def confirm(interaction):
                        data["current_times"][mod]["status_check"]["msg"] = 0
                        data["current_times"][mod]["status_check"]["next"] = (now + 1800) # 1800
                        await handleFile("current_times", "write")
                        return await interaction.response.edit_message(content = f"<t:{round(now)}:R>\nYou've confirmed your active status! Thank you for your service. :saluting_face:", embed = None, view = None)
                    button.callback = confirm
                    view = View()
                    view.add_item(button)
                    await handleFile("current_times", "write")
                    msg = await user.send(f"<t:{round(now)}:R>", embed = checkEmbed, view = view)
                    data["current_times"][mod]["status_check"]["msg"] = msg.id
                    await handleFile("current_times", "write")
                    return
        elif now > (data["current_times"][mod]["pauses"][len(data["current_times"][mod]["pauses"]) - 1] + 5400): # 5400
            return await user.send(f"Your shift has automatically ended due to being paused for over 90 minutes! It lasted for `{await endShift(mod)}` hours.")

load_dotenv()
client.run(os.getenv("TOKEN"), log_handler = handler, log_level = logging.DEBUG)