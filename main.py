import discord
import logging
import os
import json
import datetime
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, Button, View

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
    channel = client.get_channel(data["config"]["logs"])
    await channel.send(embed = msg)

async def hasData(mod):
    if mod in data["mod_data"]:
        return
    else:
        data["mod_data"][mod] = {
            "total_time": 0,
            "time_offset": 0
        }

@client.event
async def on_ready():
    print(f"Logged on as {client.user}!")

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

shift_group = app_commands.Group(name = "shift", description = "Shift system")

@shift_group.command(name = "setlogs", description = "Sets the log channel for all status updates")
async def setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    data["config"]["logs"] = channel.id
    await handleFile("config", "write")
    await interaction.response.send_message(f"Set the logs channel to {channel.mention}!")

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
    await sendLog(startedLog)

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
    data["mod_data"][mod]["length"] = length
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
    await interaction.response.send_message(f"Shift ended. {interaction.user.mention}, your shift lasted `{round(await endShift(mod), 2)}` hours!")
    endedLog = discord.Embed(
        description = f"{interaction.user.mention} has ended a shift.",
        color = discord.Color.light_grey()
    )
    await sendLog(endedLog)
    

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
    await sendLog(pausedLog)

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
    await sendLog(resumeLog)

client.tree.add_command(shift_group, guild = GUILD)
active_group = app_commands.Group(name = "active", description = "Active Hours tracker")

@active_group.command(name = "settimezone", description = "Set your active hours")
async def set(interaction: discord.Interaction):
    mod = str(interaction.user.id)
    zones1 = Select(options = [
        discord.SelectOption(label = "UTC -12:00", value = "-1200", description = "US - Baker Island"),
        discord.SelectOption(label = "UTC -11:00", value = "-1100", description = "NZ - Niue, US - American Samoa"),
        discord.SelectOption(label = "UTC -10:00", value = "-1000", description = "US - Honolulu, Hawaii"),
        discord.SelectOption(label = "UTC -09:30", value = "-930", description = "FR - Marquesas Islands"),
        discord.SelectOption(label = "UTC -09:00", value = "-900", description = "US - Alaska"),
        discord.SelectOption(label = "UTC -08:00", value = "-800", description = "US - Los Angeles, CA - Vancouver"),
        discord.SelectOption(label = "UTC -07:00", value = "-700", description = "US - Denver, CA - Calgary"),
        discord.SelectOption(label = "UTC -06:00", value = "-600", description = "MX - Mexico City, US - Chicago"),
        discord.SelectOption(label = "UTC -05:00", value = "-500", description = "US - New York, CA - Toronto"),
        discord.SelectOption(label = "UTC -04:00", value = "-400", description = "CL - Santiago, DO - Santo Domingo"),
        discord.SelectOption(label = "UTC -03:30", value = "-330", description = "CA - St. John's"),
        discord.SelectOption(label = "UTC -03:00", value = "-300", description = "BR - São Paulo, AR - Buenos Aires"),
        discord.SelectOption(label = "UTC -02:00", value = "-200", description = "DK - Greenland"),
        discord.SelectOption(label = "UTC -01:00", value = "-100", description = "Cape Verde"),
        discord.SelectOption(label = "Not Listed", value = "notlisted1", description = "For UTC +0 to +14")
    ])
    zones2 = Select(options = [
        discord.SelectOption(label = "UTC +00:00", value = "0", description = "GB - London, IE - Dublin"),
        discord.SelectOption(label = "UTC +01:00", value = "+100", description = "FR - Paris, DE - Berlin"),
        discord.SelectOption(label = "UTC +02:00", value = "+200", description = "GR - Athens, RO - Bucharest"),
        discord.SelectOption(label = "UTC +03:00", value = "+300", description = "RU - Moscow, TR - Istanbul"),
        discord.SelectOption(label = "UTC +03:30", value = "+330", description = "IR - Tehran"),
        discord.SelectOption(label = "UTC +04:00", value = "+400", description = "AE - Dubai, GE - Tbilisi"),
        discord.SelectOption(label = "UTC +04:30", value = "+430", description = "AF - Kabul"),
        discord.SelectOption(label = "UTC +05:00", value = "+500", description = "PK - Karachi, KZ - Astana"),
        discord.SelectOption(label = "UTC +05:30", value = "+530", description = "IN - Delhi, LK - Colombo"),
        discord.SelectOption(label = "UTC +05:45", value = "+545", description = "NP - Kathmandu"),
        discord.SelectOption(label = "UTC +06:00", value = "+600", description = "BD - Dhaka, KG - Bishkek"),
        discord.SelectOption(label = "UTC +06:30", value = "+630", description = "MM - Yangon"),
        discord.SelectOption(label = "UTC +07:00", value = "+700", description = "TH - Bangkok, ID - Jakarta"),
        discord.SelectOption(label = "UTC +08:00", value = "+800", description = "🔥🔥 UY PILIPINS !!!"),
        discord.SelectOption(label = "UTC +08:45", value = "+845", description = "AU - Eucla"),
        discord.SelectOption(label = "UTC +09:00", value = "+900", description = "JP - Tokyo, KR - Seoul"),
        discord.SelectOption(label = "UTC +09:30", value = "+930", description = "AU - Adelaide"),
        discord.SelectOption(label = "UTC +10:00", value = "+1000", description = "AU - Melbourne, PG - Port Moresby"),
        discord.SelectOption(label = "UTC +10:30", value = "+1030", description = "AU - Lord Howe Island"),
        discord.SelectOption(label = "UTC +11:00", value = "+1100", description = "FR - Nouméa"),
        discord.SelectOption(label = "UTC +12:00", value = "+1200", description = "NZ - Auckland, FJ - Suva"),
        discord.SelectOption(label = "UTC +12:45", value = "+1245", description = "NZ - Chatham Islands"),
        discord.SelectOption(label = "UTC +13:00", value = "+1300", description = "KI - Phoenix Islands, Samoa"),
        discord.SelectOption(label = "UTC +14:00", value = "+1400", description = "KI - Line Islands"),
        discord.SelectOption(label = "Not Listed", value = "notlisted2", description = "For UTC -12 to -1")
    ])
    async def setzone1(interaction):
        if zones1.values[0] == "notlisted1":
            setZone.remove_item(zones1)
            setZone.add_item(zones2)
            return await interaction.response.edit_message(view = setZone)
        await hasData(mod)
        data["mod_data"][mod]["time_offset"] = int(zones1.values[0])
        await handleFile("mod_data", "write")
        return await interaction.response.edit_message(content = f"You have selected {zones1.values[0]}", view = None)
    async def setzone2(interaction):
        if zones2.values[0] == "notlisted2":
            setZone.remove_item(zones2)
            setZone.add_item(zones1)
            return await interaction.response.edit_message(view = setZone)
        await hasData(mod)
        data["mod_data"][mod]["time_offset"] = int(zones2.values[0])
        await handleFile("mod_data", "write")
        return await interaction.response.edit_message(content = f"You have selected {zones2.values[0]}", view = None)
    zones1.callback = setzone1
    zones2.callback = setzone2
    setZone = View()
    setZone.add_item(zones1)
    await interaction.response.send_message(content = f"Please select your Timezone in UTC:", view = setZone)

    # setHours = Button(label = "Set Hours", style = discord.ButtonStyle.green)
    # async def hours(interaction):
    #     days = Select(min_values = 1, max_values = 7, options = [
    #         discord.SelectOption(label = "Monday"),
    #         discord.SelectOption(label = "Tuesday"),
    #         discord.SelectOption(label = "Wednesday"),
    #         discord.SelectOption(label = "Thursday"),
    #         discord.SelectOption(label = "Friday"),
    #         discord.SelectOption(label = "Saturday"),
    #         discord.SelectOption(label = "Sunday")
    #     ])
        # async def setdays(interaction):
        #     hours = Select(min_values = 0, max_values = 48, options = [
        #         discord.SelectOption(label = "12:00AM - 12:30AM", value = "0000"),
        #         discord.SelectOption(label = "12:30AM - 01:00AM", value = "0030"),
        #         discord.SelectOption(label = "01:00AM - 01:30AM", value = "0100"),
        #         discord.SelectOption(label = "01:30AM - 02:00AM", value = "0130"),
        #         discord.SelectOption(label = "02:00AM - 02:30AM", value = "0200"),
        #         discord.SelectOption(label = "02:30AM - 03:00AM", value = "0230"),
        #         discord.SelectOption(label = "03:00AM - 03:30AM", value = "0300"),
        #         discord.SelectOption(label = "03:30AM - 04:00AM", value = "0330"),
        #         discord.SelectOption(label = "04:00AM - 04:30AM", value = "0400"),
        #         discord.SelectOption(label = "04:30AM - 05:00AM", value = "0430"),
        #         discord.SelectOption(label = "05:00AM - 05:30AM", value = "0500"),
        #         discord.SelectOption(label = "05:30AM - 06:00AM", value = "0530"),
        #         discord.SelectOption(label = "06:00AM - 06:30AM", value = "0600"),
        #         discord.SelectOption(label = "06:30AM - 07:00AM", value = "0630"),
        #         discord.SelectOption(label = "07:00AM - 07:30AM", value = "0700"),
        #         discord.SelectOption(label = "07:30AM - 08:00AM", value = "0730"),
        #         discord.SelectOption(label = "08:00AM - 08:30AM", value = "0800"),
        #         discord.SelectOption(label = "08:30AM - 09:00AM", value = "0830"),
        #         discord.SelectOption(label = "09:00AM - 09:30AM", value = "0900"),
        #         discord.SelectOption(label = "09:30AM - 10:00AM", value = "0930"),
        #         discord.SelectOption(label = "10:00AM - 10:30AM", value = "1000"),
        #         discord.SelectOption(label = "10:30AM - 11:00AM", value = "1030"),
        #         discord.SelectOption(label = "11:00AM - 11:30AM", value = "1100"),
        #         discord.SelectOption(label = "11:30AM - 12:00PM", value = "1130"),
        #         discord.SelectOption(label = "12:00PM - 12:30PM", value = "1200"),
        #         discord.SelectOption(label = "12:30PM - 01:00PM", value = "1230"),
        #         discord.SelectOption(label = "01:00PM - 01:30PM", value = "1300"),
        #         discord.SelectOption(label = "01:30PM - 02:00PM", value = "1330"),
        #         discord.SelectOption(label = "02:00PM - 02:30PM", value = "1400"),
        #         discord.SelectOption(label = "02:30PM - 03:00PM", value = "1430"),
        #         discord.SelectOption(label = "03:00PM - 03:30PM", value = "1500"),
        #         discord.SelectOption(label = "03:30PM - 04:00PM", value = "1530"),
        #         discord.SelectOption(label = "04:00PM - 04:30PM", value = "1600"),
        #         discord.SelectOption(label = "04:30PM - 05:00PM", value = "1630"),
        #         discord.SelectOption(label = "05:00PM - 05:30PM", value = "1700"),
        #         discord.SelectOption(label = "05:30PM - 06:00PM", value = "1730"),
        #         discord.SelectOption(label = "06:00PM - 06:30PM", value = "1800"),
        #         discord.SelectOption(label = "06:30PM - 07:00PM", value = "1830"),
        #         discord.SelectOption(label = "07:00PM - 07:30PM", value = "1900"),
        #         discord.SelectOption(label = "07:30PM - 08:00PM", value = "1930"),
        #         discord.SelectOption(label = "08:00PM - 08:30PM", value = "2000"),
        #         discord.SelectOption(label = "08:30PM - 09:00PM", value = "2030"),
        #         discord.SelectOption(label = "09:00PM - 09:30PM", value = "2100"),
        #         discord.SelectOption(label = "09:30PM - 10:00PM", value = "2130"),
        #         discord.SelectOption(label = "10:00PM - 10:30PM", value = "2200"),
        #         discord.SelectOption(label = "10:30PM - 11:00PM", value = "2230"),
        #         discord.SelectOption(label = "11:00PM - 11:30PM", value = "2300"),
        #         discord.SelectOption(label = "11:30PM - 12:00AM", value = "2330")
        #     ])
        #     for day in days.values:
        #         async def done(interaction):
        #             yourHours = ""
        #             for hour in hours.values:
        #                 yourHours += f"\n`{hour}`"
        #                 data["active_hours"][day.lower()][hour].append(mod)
        #             await interaction.response.send_message(content = f"Your available hours for `{day}`:{yourHours}", ephemeral = True)
        #         hours.callback = done
        #         hoursView.remove_item(days)
        #         hoursView.remove_item(back)
        #         hoursView.add_item(hours)
        #         await interaction.response.send_message(content = f"Available hours for `{day}`:", view = hoursView, ephemeral = True)
        # days.callback = setdays
        # hoursView = View()
        # hoursView.add_item(days)
        # hoursView.add_item(back)
        # await interaction.response.send_message(content = f"Please select the days you are active:", view = hoursView, ephemeral = True)

@active_group.command(name = "view", description = "View your active hours")
async def set(interaction: discord.Interaction):
    return

@active_group.command(name = "disable", description = "Temporarily disables your active hours")
async def set(interaction: discord.Interaction):
    return

@active_group.command(name = "enable", description = "Re-enables your active hours")
async def set(interaction: discord.Interaction):
    return

client.tree.add_command(active_group, guild = GUILD)

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

@tasks.loop(seconds = 30)
async def status_check():
    tempdict = data["current_times"]
    for mod in tempdict:
        now = round(datetime.datetime.now().timestamp())
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
                    await handleFile("current_times", "write")
                    return
        elif now > (data["current_times"][mod]["pauses"][len(data["current_times"][mod]["pauses"]) - 1] + 5400): # 5400
            await user.send(f"Your shift has automatically ended due to being paused for over 90 minutes! It lasted for `{round(await endShift(mod), 2)}` hours.")
            forceEndedLog = discord.Embed(
                description = f"{user.mention}'s shift has ended after 90 minutes on pause.",
                color = discord.Color.red()
            )
            return await sendLog(forceEndedLog)

load_dotenv()
client.run(os.getenv("TOKEN"), log_handler = handler, log_level = logging.DEBUG)