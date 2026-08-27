import discord
import logging
import os
import json
import datetime
import math
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View

data = {"mod_data": dict({}), "current_times": dict({}), "active_hours": dict({}), "config": dict({}), "offline_save": dict({})}

async def handleFile(name, method):
    if method == "read":
        with open("./data/" + name + ".json", "r", encoding = "utf-8") as f: data[name] = json.load(open("./data/" + name + ".json"))
    else:
        with open("./data/" + name + ".json", "w", encoding = "utf-8") as f: json.dump(data[name], f, ensure_ascii = False, indent = 4)

GUILD = discord.Object(id = 1238093282852999229)

handler = logging.FileHandler(filename = "bot.log", encoding = "utf-8", mode = "w")
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
client = commands.Bot(command_prefix = "p!", intents = intents)

async def isOffline():
    if len(data["current_times"]) > 0:
        print(f"Bot offline! Saving shifts.")
        tempdict = data["current_times"]
        for mod in tempdict:
            end = await endShift(mod)
            print(f"Saved shift for {mod}")
            data["offline_save"][mod] = end
            await handleFile("offline_save", "write")
        return print(f"Shifts saved!")

async def sendLog(msg):
    if data["config"]["logs"] == 0:
        return
    channel = client.get_channel(data["config"]["logs"])
    await channel.send(embed = msg)

async def hasData(mod):
    if mod in data["mod_data"]:
        return
    else:
        data["mod_data"][mod] = {
            "total_time": 0,
            "time_offset": 0,
            "hours": {
                "active": True,
                "times": {
                    "monday": [],
                    "tuesday": [],
                    "wednesday": [],
                    "thursday": [],
                    "friday": [],
                    "saturday": [],
                    "sunday": []
                }
            }
        }

@client.event
async def on_ready():
    print(f"Logged on as {client.user}!")
    status_check.start()
    onduty_check.start()

    try:
        for key in data:
            await handleFile(key, "read")
            print(f"Read file {key}.json")
        pass
    except Exception as err:
        print(f"Error reading file data: {err}")

    try:
        synced = await client.tree.sync(guild = GUILD)
        print(f"Synced {len(synced)} commands to guild {GUILD.id}")
        pass
    except Exception as err:
        print(f"Error syncing commands: {err}")

    try:
        if len(data["offline_save"]) > 0:
            preCrash = discord.Embed(
                title = "Bot lost connection!",
                description = "The following are shifts that have been saved:"
            )
            for mod in data["offline_save"]:
                user = client.get_user(int(mod))
                preCrash.add_field(
                    name = f"{user.name}",
                    value = f"{user.mention} - `{round(data['offline_save'][mod] / 3600, 2)}` hours.",
                    inline = False
                )
                data["offline_save"].pop(mod, None)
            await handleFile("offline_save", "write")
            await sendLog(preCrash)
    except Exception as err:
        print(f"Error sending disconnection report: {err}")

@client.event
async def on_disconnect():
    print("Client disconnected!")
    await isOffline()

shift_group = app_commands.Group(name = "shift", description = "Shift system", default_permissions = discord.Permissions(manage_messages = True))

@shift_group.command(name = "start", description = "Set your status to currently moderating")
async def start(interaction: discord.Interaction, dms: bool=False):
    now = round(datetime.datetime.now().timestamp())
    details = {
        "start": now,
        "dms": False,
        "paused": False,
        "pauses": [],
        "status_check": {
            "msg": 0,
            "next": (now + 1200) # 1200
        }
    }
    if dms:
        details["dms"] = True
    mod = str(interaction.user.id)
    if mod in data["current_times"]:
        return await interaction.response.send_message(f"You already started a shift <t:{data['current_times'][mod]['start']}:R> ago!", ephemeral = True)
    data["current_times"][mod] = details
    await handleFile("current_times", "write")
    await interaction.response.send_message(f"{interaction.user.mention} has started a shift, check your DMs!")
    startedEmbed = discord.Embed(
        title = "Shift started!",
        description = f"Hi {interaction.user.mention}! You have started a shift in Sining Gang, meaning that you are now actively moderating the server, and your status will be updated for all members to see. This bot will periodically be DMing you to check if you're still active, so please read the instructions once it does.\n\nTo end your shift, run `/shift_end`.",
        color = discord.Color.blurple()
    )
    startedEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")
    await interaction.user.send(embed = startedEmbed)

    startedLog = discord.Embed(
        description = f"{interaction.user.mention} has started a shift.",
        color = discord.Color.green()
    )
    return await sendLog(startedLog)

async def resumeShift(mod):
    now = round(datetime.datetime.now().timestamp())
    data["current_times"][mod]["paused"] = False
    last_entry = len(data["current_times"][mod]["pauses"]) - 1
    data["current_times"][mod]["pauses"][last_entry] = (now - data["current_times"][mod]["pauses"][last_entry])
    data["current_times"][mod]["status_check"]["next"] = (now + 1200) # 1200
    await handleFile("current_times", "write")

async def endShift(mod):
    end = round(datetime.datetime.now().timestamp())
    user = client.get_user(int(mod))
    lastCheck = data["current_times"][mod]["status_check"]["msg"]
    if lastCheck > 0:
        check = await user.fetch_message(lastCheck)
        await check.edit(content = f"<t:{end}:R>\n> Status Check cancelled as the shift has ended.", embed = None, view = None)
    elif data["current_times"][mod]["paused"]:
        await resumeShift(mod)
    start = data["current_times"][mod]["start"]
    length = end - start
    await hasData(mod)
    data["mod_data"][mod]["total_time"] = length
    for pause in data["current_times"][mod]["pauses"]:
        length -= pause
    data["current_times"].pop(mod, None)
    await handleFile("current_times", "write")
    await handleFile("mod_data", "write")
    return length

@shift_group.command(name = "end", description = "Ends your current moderating status")
async def end(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!", ephemeral = True)
    await interaction.response.send_message(f"Shift ended. {interaction.user.mention}, your shift lasted `{round(await endShift(mod)/3600, 2)}` hours!")
    endedLog = discord.Embed(
        description = f"{interaction.user.mention} has ended a shift.",
        color = discord.Color.light_grey()
    )
    return await sendLog(endedLog)

async def pauseShift(mod):
    now = round(datetime.datetime.now().timestamp())
    data["current_times"][mod]["paused"] = True
    data["current_times"][mod]["pauses"].append(now)
    await handleFile("current_times", "write")


@shift_group.command(name = "pause", description = "Pauses your shift, automatically stops it after 90 minutes")
async def pause(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!", ephemeral = True)
    if data["current_times"][mod]["paused"]:
        return await interaction.response.send_message(f"Shift already paused!", ephemeral = True)
    await pauseShift(mod)
    await interaction.response.send_message("Shift paused!")
    pausedLog = discord.Embed(
        description = f"{interaction.user.mention}'s shift has been paused.",
        color = discord.Color.yellow()
    )
    return await sendLog(pausedLog)

@shift_group.command(name = "continue", description = "Continues your shift if it is paused")
async def cont(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    if not mod in data["current_times"]:
        return await interaction.response.send_message(f"You have not started a shift!", ephemeral = True)
    if not data["current_times"][mod]["paused"]:
        return await interaction.response.send_message(f"Shift is not paused!", ephemeral = True)
    await resumeShift(mod)
    await interaction.response.send_message("Shift continued!")
    resumeLog = discord.Embed(
        description = f"{interaction.user.mention} has resumed a shift.",
        color = discord.Color.blue()
    )
    return await sendLog(resumeLog)

client.tree.add_command(shift_group, guild = GUILD)
active_group = app_commands.Group(name = "active", description = "Active Hours tracker", default_permissions = discord.Permissions(manage_messages = True))

def convertZone(text):
    return int(text.replace(':', '')) / 100

zones = ["-12:00", "-11:00", "-10:00", "-09:30", "-09:00", "-08:00", "-07:00", "-06:00", "-05:00", "-04:00", "-03:30", "-03:00", "-02:00", "-01:00", "+00:00", "+01:00", "+02:00", "+03:00", "+03:30", "+04:00", "+04:30", "+05:00", "+05:30", "+05:45", "+06:00", "+06:30", "+07:00", "+08:00", "+08:45", "+09:00", "+09:30", "+10:00", "+10:30", "+11:00", "+12:00", "+12:45", "+13:00", "+14:00"]
days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
hours = {"12:00am": "0000", "12:15am": "0015", "12:30am": "0030", "12:45am": "0045", "01:00am": "0100", "01:15am": "0115", "01:30am": "0130", "01:45am": "0145", "02:00am": "0200", "02:15am": "0215", "02:30am": "0230", "02:45am": "0245", "03:00am": "0300", "03:15am": "0315", "03:30am": "0330", "03:45am": "0345", "04:00am": "0400", "04:15am": "0415", "04:30am": "0430", "04:45am": "0445", "05:00am": "0500", "05:15am": "0515", "05:30am": "0530", "05:45am": "0545", "06:00am": "0600", "06:15am": "0615", "06:30am": "0630", "06:45am": "0645", "07:00am": "0700", "07:15am": "0715", "07:30am": "0730", "07:45am": "0745", "08:00am": "0800", "08:15am": "0815", "08:30am": "0830", "08:45am": "0845", "09:00am": "0900", "09:15am": "0915", "09:30am": "0930", "09:45am": "0945", "10:00am": "1000", "10:15am": "1015", "10:30am": "1030", "10:45am": "1045", "11:00am": "1100", "11:15am": "1115", "11:30am": "1130", "11:45am": "1145", "12:00pm": "1200", "12:15pm": "1215", "12:30pm": "1230", "12:45pm": "1245", "01:00pm": "1300", "01:15pm": "1315", "01:30pm": "1330", "01:45pm": "1345", "02:00pm": "1400", "02:15pm": "1415", "02:30pm": "1430", "02:45pm": "1445", "03:00pm": "1500", "03:15pm": "1515", "03:30pm": "1530", "03:45pm": "1545", "04:00pm": "1600", "04:15pm": "1615", "04:30pm": "1630", "04:45pm": "1645", "05:00pm": "1700", "05:15pm": "1715", "05:30pm": "1730", "05:45pm": "1745", "06:00pm": "1800", "06:15pm": "1815", "06:30pm": "1830", "06:45pm": "1845", "07:00pm": "1900", "07:15pm": "1915", "07:30pm": "1930", "07:45pm": "1945", "08:00pm": "2000", "08:15pm": "2015", "08:30pm": "2030", "08:45pm": "2045", "09:00pm": "2100", "09:15pm": "2115", "09:30pm": "2130", "09:45pm": "2145", "10:00pm": "2200", "10:15pm": "2215", "10:30pm": "2230", "10:45pm": "2245", "11:00pm": "2300", "11:15pm": "2315", "11:30pm": "2330", "11:45pm": "2345", "11:59pm": "2400"}

def convertTime(time, offset, day):
    offset = offset - 8
    time = convertZone(time)
    min, hour = math.modf(time)
    offmin, offhour = math.modf(offset)
    min = round(min * 100)
    offmin = round(offmin * 100)
    finalmin = (min + offmin)/60
    finalhour = hour + offhour
    def changeDay(day, change):
        index = days.index(day) + change
        if index < 0:
            day = "sunday"
        elif index > 6:
            day = "monday"
        else:
            day = days[index]
    min, hour = math.modf(finalmin)
    finalmin = min * 6
    finalhour += hour
    if finalhour < 0:
        finalhour = 24 - finalhour
        changeDay(day, -1)
    elif finalhour > 24:
        finalhour = finalhour - 24
        changeDay(day, 1)
    finalmin = str(finalmin).replace('.', '')
    finalhour = str(int(finalhour))
    if len(finalhour) < 2:
        finalhour = "0" + finalhour
    time = finalhour + finalmin
    return time, day

async def setDays(interaction, yourDays):
    def checkauth(m):
        return m.author == interaction.user
    channel = interaction.channel
    toSend = f""
    toSend = f"Please input the days you are active. Example:\n```Monday, Friday, Saturday, Sunday```"
    await channel.send(content = toSend)
    msg = await client.wait_for("message", timeout = 300, check = checkauth)
    if msg.content == "cancel":
        return await channel.send("Cancelled!")
    else:
        tempDays = [day.strip() for day in str(msg.content).lower().split(',')]
        for aDay in tempDays:
            if aDay in days:
                yourDays.append(aDay)
            else:
                await channel.send(f"{aDay} is an invalid day! Please try again.")
                return await setDays(channel, set, yourDays)
    return yourDays

def removeHours(mod, day):
    for hour in data["active_hours"][day]:
        index = 0
        try:
            index = data["active_hours"][day][hour].index(mod)
        except:
            continue
        data["active_hours"][day][hour].pop(index)

async def setHours(mod, interaction, yourDays):
    def checkauth(m):
        return m.author == interaction.user
    channel = interaction.channel
    offset = data["mod_data"][mod]["time_offset"]
    for day in yourDays:
        removeHours(mod, day)
        await channel.send(f"Please input your active times for `{day}` in your timezone! Example:\n```12:00PM - 04:00PM, 06:00PM - 09:00PM```")
        toSend = f"Your Active Hours for `{day}`:\n"
        msg = await client.wait_for("message", timeout = 300, check = checkauth)
        if msg.content == "cancel":
            return await channel.send("Cancelled!")
        time = [day.strip() for day in str(msg.content).lower().split(',')]
        toEdit = await channel.send(content = toSend)
        data["mod_data"][mod]["hours"]["times"][day] = []
        for span in time:
            if span not in data["mod_data"][mod]["hours"]["times"][day]:
                data["mod_data"][mod]["hours"]["times"][day].append(span)
                split = [mark.strip() for mark in span.split('-')]
                start = split[0]
                middle = False
                end = split[1]
                for hour in hours:
                    if hour == start:
                        middle = True
                        pass
                    elif middle == False:
                        continue
                    elif hour == end:
                        middle = False
                        toSend += f"`{span}`\n"
                        await toEdit.edit(content = toSend)
                        break
                    time, newDay = convertTime(hours[hour], offset, day)
                    if mod in data["active_hours"][newDay][time]:
                        continue
                    data["active_hours"][newDay][time].append(mod)
                await handleFile("active_hours", "write")
                await handleFile("mod_data", "write")

@active_group.command(name = "set", description = "Set your active hours")
async def setzone(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    await interaction.response.send_message("Setup started! Please follow the instructions and examples exactly as presented.", ephemeral = True)
    channel = interaction.channel
    def checkauth(m):
        return m.author == interaction.user
    async def startsetup():
        await interaction.followup.send(f"Please input your Timezone in UTC offset. For example, if you're in the Philippines just send:\n```+08:00```\n\nTo skip this step, input `skip`\nTo cancel anytime, input `cancel`")
        msg = await client.wait_for("message", timeout = 60, check = checkauth)
        await hasData(mod)
        if not msg.content == "skip":
            timezone = convertZone(msg.content)
            data["mod_data"][mod]["time_offset"] = timezone
            await handleFile("mod_data", "write")
        elif msg.content == "cancel":
            return channel.send("Active hours setup cancelled!")
        elif msg.content == "skip" and data["mod_data"][mod]["time_offset"] == 0:
            await channel.send("You need to set your Timezone in order to continue the setup!")
            return await startsetup()
        else:
            pass
    await startsetup()
    yourDays = []
    await setDays(interaction, yourDays)
    await setHours(mod, interaction, yourDays)
    return await channel.send(f"You've succesfully set up your Active Hours!")

@active_group.command(name = "view", description = "View your active hours")
async def view(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    viewmsg = f"Your active dates and times:\n"
    for day in data["mod_data"][mod]["hours"]["times"]:
        if len(data["mod_data"][mod]["hours"]["times"][day]) > 0:
            viewmsg += f"\n**{day}**:\n"
            for span in data["mod_data"][mod]["hours"]["times"][day]:
                viewmsg += f"`{span}`\n"
        else:
            pass
    return await interaction.response.send_message(content = viewmsg)

@active_group.command(name = "change", description = "Change your active hours")
async def modify(interaction: discord.Interaction):
    def checkauth(m):
        return m.author == interaction.user
    mod = str(interaction.user.id)
    await interaction.response.send_message("Setting up Active Hours.", ephemeral = True)
    yourDays = []
    await setDays(interaction, yourDays)
    await setHours(mod, interaction, yourDays)
    return await interaction.channel.send("Process completed!")

@active_group.command(name = "clear", description = "Clears all your active hours")
async def clear(interaction: discord.Interaction):
    def checkauth(m):
        return m.author == interaction.user
    mod = str(interaction.user.id)
    await interaction.response.send_message("ARE YOU SURE cus like this will delete ALL your active hours, you could `/active disable` instead maybe..\nInput: `YES/NO`")
    msg = await client.wait_for("message", timeout = 60, check = checkauth)
    if msg.content == "YES":
        for day in data["active_hours"]:
            removeHours(mod, day)
            for time in data["mod_data"][mod]["hours"]["times"][day]:
                index = data["mod_data"][mod]["hours"]["times"][day].index(time)
                data["mod_data"][mod]["hours"]["times"][day].pop(index)
        data["mod_data"][mod]["hours"]["active"] = True
        await handleFile("active_hours", "write")
        await handleFile("mod_data", "write")
        return await interaction.channel.send("Done deleted em all")
    elif msg.content == "NO":
        return await interaction.channel.send("Ok guess not 🤷‍♀️😋")

@active_group.command(name = "disable", description = "Temporarily disables your active hours")
async def disable(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    data["mod_data"][mod]["hours"]["active"] = False
    await handleFile("mod_data", "write")
    return await interaction.response.send_message("Temporarily disabled your active hours! You will no longer be reminded, or shown on the On-Duty Display.")

@active_group.command(name = "enable", description = "Re-enables your active hours")
async def enable(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    data["mod_data"][mod]["hours"]["active"] = True
    await handleFile("mod_data", "write")
    return await interaction.response.send_message("Re-enabled your active hours! You will be reminded, and shown on the On-Duty Display.")

client.tree.add_command(active_group, guild = GUILD)

help_group = app_commands.Group(name = "help", description = "Information on the bot and its commands", default_permissions = discord.Permissions(manage_messages = True))

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
    return await interaction.response.send_message(embed = helpEmbed)

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
    return await interaction.response.send_message(embed = shiftEmbed)

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
    return await interaction.response.send_message(embed = activeEmbed)

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
    return await interaction.response.send_message(embed = ondutyEmbed)

client.tree.add_command(help_group, guild = GUILD)

admin_group = app_commands.Group(name = "admin", description = "Admins onleh", default_permissions = discord.Permissions(administrator = True))

@admin_group.command(name = "setlogs", description = "Sets the log channel for all status updates")
async def setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    data["config"]["logs"] = channel.id
    await handleFile("config", "write")
    return await interaction.response.send_message(f"Set the logs channel to {channel.mention}!")

emptyDisplayEmbed = discord.Embed(
    title = "Available Moderators",
    description = "There are currently no available moderators, feel free to open a <#1522890700016848987> if you require assistance!",
    color = discord.Color.red()
)
emptyDisplayEmbed.set_thumbnail(url = "https://cdn.discordapp.com/attachments/1524742910975938630/1530480633569083503/Untitled88_20260725153955.png?ex=6a913c29&is=6a8feaa9&hm=e349b012b65fe7e32c215b4f2b9e6c2f16b65a5ecd5da11ea3c0933244cc28cd&animated=true")

displayEmbed = discord.Embed(
    title = "Available Moderators",
    description = "The following moderators are currently available! You are free to ping the ones **On-Duty** if you have any concerns that need immediate attention. If there are currently no mods on-duty, please notify an online mod under **Available**.",
    color = discord.Color.green()
)
displayEmbed.set_thumbnail(url = "https://cdn.discordapp.com/icons/1522861009386209320/a_d38d426dbc09afb9d94859870cf4cf47.webp?size=512&animated=true")

async def setupDisplay():
    embed = discord.Embed()
    if len(data["config"]["display"]["on_duty"]) > 0 or len(data["config"]["display"]["active"]) > 0:
        embed = displayEmbed.copy()
        onduty = f""
        active = f""
        if len(data["config"]["display"]["on_duty"]) > 0:
            for mod in data["config"]["display"]["on_duty"]:
                if data["current_times"][mod]["dms"]:
                    onduty += f"<@{mod}> - DMs open\n"
                else:
                    onduty += f"<@{mod}>\n"
        if len(data["config"]["display"]["active"]) > 0:
            for mod in data["config"]["display"]["active"]:
                if data["mod_data"][mod]["hours"]["active"]:
                    active += f"<@{mod}>\n"
                else:
                    continue
        embed.add_field(
            name = "On-Duty",
            value = onduty,
            inline = False
        )
        embed.add_field(
            name = "Available",
            value = active,
            inline = False
        )
    else:
        embed = emptyDisplayEmbed
    return embed

@admin_group.command(name = "onduty", description = "Sends a new On-Duty Display message")
async def setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    toEmbed = discord.Embed()
    if data["config"]["display"]["msg"] == 0:
        toEmbed = await setupDisplay()
        display = await channel.send(embed = toEmbed)
        data["config"]["display"]["msg"] = display.id
        data["config"]["display"]["channel"] = channel.id
        await handleFile("config", "write")
    oldChannel = client.get_channel(int(data["config"]["display"]["channel"]))
    oldDisplay = await oldChannel.fetch_message(data["config"]["display"]["msg"])
    await oldDisplay.delete()
    toEmbed = await setupDisplay()
    display = await channel.send(embed = toEmbed)
    data["config"]["display"]["msg"] = display.id
    data["config"]["display"]["channel"] = channel.id
    await handleFile("config", "write")
    return await interaction.response.send_message(f"Sent a new On-Duty Display message to {channel.mention}!")

client.tree.add_command(admin_group, guild = GUILD)

@tasks.loop(seconds = 10)
async def onduty_check():
    if data["config"]["display"]["msg"] == 0:
        return
    timestamp = datetime.datetime.now()
    now = timestamp.strftime('%H%M')
    day = timestamp.strftime('%A').lower()
    onduty = []
    active = []
    if len(data["current_times"]) > 0:
        for mod in data["current_times"]:
            if data["current_times"][mod]["paused"]:
                continue
            onduty.append(mod)
    for hour in data["active_hours"][day]:
        if int(hour) - int(now) >= 0 and int(hour) - int(now) <= 15:
            if len(data["active_hours"][day][hour]) > 0:
                for mod in data["active_hours"][day][hour]:
                    if mod in onduty:
                        continue
                    active.append(mod)
        else:
            continue
    data["config"]["display"]["on_duty"] = onduty
    data["config"]["display"]["active"] = active
    await handleFile("config", "write")
    channel = client.get_channel(int(data["config"]["display"]["channel"]))
    display = await channel.fetch_message(data["config"]["display"]["msg"])
    toEmbed = await setupDisplay()
    if toEmbed == display.embeds[0]:
        return
    else:
        return await display.edit(embed = toEmbed)

@tasks.loop(minutes = 1)
async def status_check():
    tempdict = data["current_times"].copy()
    now = round(datetime.datetime.now().timestamp())
    for mod in tempdict:
        user = client.get_user(int(mod))
        if not data["current_times"][mod]["paused"]:
            if now > data["current_times"][mod]["status_check"]["next"]:
                if now > (data["current_times"][mod]["status_check"]["next"] + 600): # 600
                    check = await user.fetch_message(data["current_times"][mod]["status_check"]["msg"])
                    await pauseShift(mod)
                    await check.edit(view = None)
                    await user.send(f"You did not confirm your status and your shift has been paused!\nPlease unpause your shift by running `/shift continue`, else it will automatically end <t:{now + 5400}:R>.")
                    forcePausedLog = discord.Embed(
                        description = f"{user.mention}'s shift has been paused due to not responding to the status check.",
                        color = discord.Color.orange()
                    )
                    return await sendLog(forcePausedLog)
                elif data["current_times"][mod]["status_check"]["msg"] == 0:
                    checkEmbed = discord.Embed(
                        title = "Status Check",
                        description = "Hello! If you're still here, please click the reaction down below. If you don't react within 10 minutes, your shift will be paused. Thank you!",
                        color = discord.Color.random()
                    )
                    button = Button(label = "Still here!", style = discord.ButtonStyle.primary, emoji = "<:teehee:1524809416149569588>")
                    async def confirm(interaction):
                        data["current_times"][mod]["status_check"]["msg"] = 0
                        data["current_times"][mod]["status_check"]["next"] = (now + 1200) # 1200
                        await handleFile("current_times", "write")
                        return await interaction.response.edit_message(content = f"<t:{now}:R>\nYou've confirmed your active status! Thank you for your service. :saluting_face:", embed = None, view = None)
                    button.callback = confirm
                    view = View()
                    view.add_item(button)
                    await handleFile("current_times", "write")
                    msg = await user.send(f"<t:{now}:R>", embed = checkEmbed, view = view)
                    data["current_times"][mod]["status_check"]["msg"] = msg.id
                    return await handleFile("current_times", "write")
        elif now > (data["current_times"][mod]["pauses"][len(data["current_times"][mod]["pauses"]) - 1] + 5400): # 5400
            await user.send(f"Your shift has automatically ended due to being paused for over 90 minutes! It lasted for `{round(await endShift(mod)/3600, 2)}` hours.")
            forceEndedLog = discord.Embed(
                description = f"{user.mention}'s shift has ended after 90 minutes on pause.",
                color = discord.Color.red()
            )
            return await sendLog(forceEndedLog)

load_dotenv()
client.run(os.getenv("TOKEN"), log_handler = handler, log_level = logging.DEBUG)