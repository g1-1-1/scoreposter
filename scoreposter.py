import requests
import os
import re
from typing import List
from rosu_pp_py import Beatmap, Calculator
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

load_dotenv()

mods = [
    (1, "NF"),
    (2, "EZ"),
    (4, "TD"),
    (8, "HD"),
    (16, "HR"),
    (32, "SD"),
    (64, "DT"),
    (128, "RX"),
    (256, "HT"),
    (512, "NC"),
    (1024, "FL"),
    (2048, "AT"),
    (4096, "SO"),
    (8192, "AP"),
    (16384, "PF"),
]

def int_to_readable(value: int) -> List[str]:
    if value == 0:
        return []
    else:
        return [name for mod, name in mods if value & mod]

# get keys for osu and discord
osu_api_key = os.getenv("osu_api_key")
discord_token = os.getenv("discord_token")

# check the user has put the api keys in the .env file

if osu_api_key == "EDIT THIS WITH YOUR API KEY":
    print("You need to add the osu API key in the .env file!")
    exit()

elif discord_token == "EDIT THIS WITH YOUR DISCORD BOT TOKEN":
    print("You need to add the discord bot token in the .env file!")
    exit()

def scorepost(username : str, link : bool):

    # make a request to the osu! API to retrieve the user's most recent play
    if link == False:
        inital_response_user = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={osu_api_key}&u={username}&limit=1")
        print(f"making initial score request for {username}...")

        # parse the response as JSON
        initial_data = inital_response_user.json()

    #regex to check if it's a score link

    elif link and re.search("https://osu\.ppy\.sh/scores/[a-zA-Z]+//([1-9][0-9]*)|0/", username):
        initial_response_link = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={osu_api_key}&u={username}&limit=1")
        print(f"making initial score request for {username}...")

        # parse the response as JSON
        initial_data = initial_response_link.json()
    
    elif link and re.search("https://osu\.ppy\.sh/scores/[a-zA-Z]+//([1-9][0-9]*)|0/", username) == False:
        return "Not an osu! score link"

    # extract the relevant information from the response
    beatmap_id, score_max, n300, n100, n50, nmiss, perfect, int_mods = (
        initial_data[0]["beatmap_id"], 
        initial_data[0]["maxcombo"], 
        int(initial_data[0]["count300"]), 
        int(initial_data[0]["count100"]), 
        int(initial_data[0]["count50"]), 
        int(initial_data[0]["countmiss"]), 
        initial_data[0]["perfect"], 
        int(initial_data[0]["enabled_mods"])
    )
    # accuracy = format(min(100.0 * ((n300 * 300.0) + (n100 * 100.0) + (n50 * 50.0)) / ((n300 + n100 + n50 + nmiss) * 300.0), 100), '.2f')
    # accuracy = (n300 + n100 + n50 / 2) / (n300 + n100 + n50 + nmiss)
    accuracy = 100*((300*n300 + 100*n100 + 50*n50) / (300*(n300 + n100 + n50 + nmiss)))
    formatted_accuracy = format(accuracy, '.2f')
    readable_mods = int_to_readable(int(int_mods))

    print(f"{n300} {n100} {n50} {nmiss}")

    print("done!")

    print("making the score's map request...")
    map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={osu_api_key}&b={beatmap_id}&limit=1")
    map_data = map_response.json()

    artist, title, creator, diff, map_max = (
        map_data[0]["artist"],
        map_data[0]["title"],
        map_data[0]["creator"],
        map_data[0]["version"],
        map_data[0]["max_combo"],
    )

    print("done!")
    print(f"creating the scorepost for {username} latest's play...")

    mods = "" if int_mods == 0 else " +" + ''.join(readable_mods)

    get_osu_file = requests.get(f"https://old.ppy.sh/osu/{beatmap_id}", stream=True)

    with open("beatmap.osu", "wb") as f:
        for chunk in get_osu_file.iter_content(chunk_size=8192):
            f.write(chunk)

    map = Beatmap(bytes=open("beatmap.osu", "rb").read())
    calc = Calculator(mode=0, mods=int(int_mods))
    calc.set_acc(accuracy)
    calc.set_n300(n300)
    calc.set_n100(n100)
    calc.set_n50(n50)
    calc.set_n_misses(nmiss)
    calc.set_combo(int(score_max))

    pp = calc.performance(map)
    sr = round(float(pp.difficulty.stars), 2)

    if perfect == 1:
        combo = "FC"
        max_pp_string = ""
    else:
        miss_string = f" {nmiss}❌ "
        combo = f"{score_max}x/{map_max}x"
        calc.set_n_misses(0)
        calc.set_combo(int(map_max))
        max_pp = calc.performance(map)
        max_pp_string = f"({round(max_pp.pp)}pp if FC)"

    scorepost = f"{username} | {artist} - {title} [{diff}] (mapped by {creator}, {sr}*){mods} {formatted_accuracy}% {combo}{miss_string}{round(pp.pp)}pp {max_pp_string} "

    return scorepost


# start discord bot

bot = commands.Bot(command_prefix='.', intents=discord.Intents.none())

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("osu!"))
    print("Discord bot is up")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


# command for discord to request the scorepost from last play

@bot.tree.command(name="scorepost", description="This command will generate a scorepost title you can use in /r/osugame from an user's last play")
@app_commands.describe(osu_user="The username of the player you want to generate a scorepost title")
@app_commands.rename(osu_user="username")
async def scoreposter(interaction: discord.Interaction, osu_user : str):
    await interaction.response.send_message(f"```{scorepost(osu_user, False)}```", ephemeral=False)

# command for discord to request scorepost from link

@bot.tree.command(name="scorepost-link", description="This command will generate a scorepost title you can use in /r/osugame from a score link")
@app_commands.describe(score_link="The link of the score you want to generate a scorepost title")
@app_commands.rename(score_link="score-link")
async def scoreposter(interaction: discord.Interaction, score_link : str):
    await interaction.response.send_message(f"{scorepost(score_link, True)}", ephemeral=False)
    

bot.run(discord_token)



