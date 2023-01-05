import requests
import os
from random import choice
from typing import List, Literal
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


def int_to_readable(value: int) -> List[str]:
    mod_names = [name for mod, name in mods if value & mod]

    # Check for invalid combinations
    if "SD" in mod_names and "PF" in mod_names:
        mod_names.remove("SD")
        return mod_names
    if "DT" in mod_names and "NC" in mod_names:
        # Remove "DT" and return "HD" and "NC"
        mod_names.remove("DT")
        return mod_names

    return mod_names

def int_to_santised_int(value: int) -> int:
    if value == 0:
        return 0
    else:
        mods_to_check = [1024, 512, 256, 64, 16, 8, 2] # FL, NC, HT, DT, HR, HD, EZ
        combined_value = 0
        for mod in mods_to_check:
            if value & mod:
                combined_value |= mod
        return combined_value

def extract_initial_data(initial_data):
    try:
        beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods, score_id = (
            initial_data[0]["beatmap_id"], 
            initial_data[0]["rank"],
            int(initial_data[0]["maxcombo"]), 
            int(initial_data[0]["count300"]), 
            int(initial_data[0]["count100"]), 
            int(initial_data[0]["count50"]), 
            int(initial_data[0]["countmiss"]), 
            initial_data[0]["perfect"], 
            int_to_santised_int(int(initial_data[0]["enabled_mods"])),
            initial_data[0]["score_id"]
        )
    except IndexError as e:
        print(f"an exception occurred: '{e}'; that user probably doesn't have any data available.")
        raise
    return beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods, score_id

def extract_map_data(map_data):
    artist, title, creator, diff, map_max, circles, sliders, spinners, mode = (
        map_data[0]["artist"],
        map_data[0]["title"],
        map_data[0]["creator"],
        map_data[0]["version"],
        int(map_data[0]["max_combo"]),
        int(map_data[0]["count_normal"]),
        int(map_data[0]["count_slider"]),
        int(map_data[0]["count_spinner"]),
        int(map_data[0]["mode"])
    )
    return artist, title, creator, diff, map_max, circles, sliders, spinners, mode

def mode_to_string(mode):
    modes = {
        0: "osu!",
        1: "osu!taiko",
        2: "osu!catch",
        3: "osu!mania"
    }
    return modes.get(mode, os.getenv("default_mode"))

def mode_to_url_string(mode):
    modes = {
        0: "osu",
        1: "taiko",
        2: "fruits",
        3: "mania"
    }
    return modes.get(mode, os.getenv("default_mode"))

def string_to_mode(mode):
    modes = {
            "osu!std" : 0,
            "osu!taiko" : 1,
            "osu!catch" : 2,
            "osu!mania" : 3
        }
    return modes[mode]

def scorepost(username : str, ruleset : str):

    # map mode to numbers
    gamemode = string_to_mode(ruleset)

    # make a request to the osu! API to retrieve the user's most recent play

    print(f"making initial score request for {username}...")
    initial_response_user = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={osu_api_key}&u={username}&m={gamemode}&limit=1")

    # parse the response as JSON
    
    initial_data = initial_response_user.json()

    if initial_data == []:
        return f"No plays done by {username} on {ruleset} recently"
    # extract the relevant information from the response

    beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods, score_id = extract_initial_data(initial_data)
    readable_mods = int_to_readable(int(int_mods))

    print("done!")
    print("making the score's map request...")

    map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={osu_api_key}&b={beatmap_id}&limit=1")
    map_data = map_response.json()
    artist, title, creator, diff, map_max, circles, sliders, spinners, mode = extract_map_data(map_data)

    print("done!")
    print(f"creating the scorepost for {username} latest's play...")

    try:
        # grab the .osu file so we can do calculations locally
        get_osu_file = requests.get(f"https://old.ppy.sh/osu/{beatmap_id}", stream=True)
        # open the .osu file we captured
        with open("beatmap.osu", "wb") as f:
            for chunk in get_osu_file.iter_content(chunk_size=8192):
                f.write(chunk)
    except:
        print(".osu file was unreachable, exiting!")
        raise InterruptedError

    readable_mods = int_to_readable(int(int_mods))
    mods = " +" + ''.join(readable_mods) if int_mods != 0 else ""
    accuracy = min(100.0 * ((n300 * 300.0) + (n100 * 100.0) + (n50 * 50.0)) / ((n300 + n100 + n50 + nmiss) * 300.0), 100)

    map = Beatmap(bytes=open("beatmap.osu", "rb").read())
    calc = Calculator(mode=mode)
    calc.set_acc(accuracy)
    calc.set_mods(int_mods)
    calc.set_n_misses(nmiss)
    calc.set_combo(score_max)

    pp = calc.performance(map)
    sr = round(float(pp.difficulty.stars), 2)
    if score_max - 20 >= map_max is True:
        combo = "FC "
        max_pp_string = ""
        miss_string = ""
    elif nmiss == 0:
        combo = f"{int(score_max):,}x/{int(map_max):,}x "
        max_pp_string = ""
        miss_string = ""
    else:
        miss_string = f" {nmiss}❌ "
        combo = f"{int(score_max):,}/{int(map_max):,}x"
        calc.set_n_misses(0)
        calc.set_combo(int(map_max))
        calc.set_mods(int_mods)
        max_pp = calc.performance(map)
        max_pp_string = f"({round(max_pp.pp):,}pp if FC)"

    scorepost = f"{f'[{mode_to_string(gamemode)}] ' if int(gamemode) != 0 else ''}{username} | {artist} - {title} [{diff}] ({creator}, {sr}⭐️){mods} {accuracy:.2f}% {combo}{miss_string}| {round(pp.pp):,}pp {max_pp_string} ".replace("%20", " ").replace("HDDTNC", "HDNC")
    
    return scorepost

# start discord bot

bot = commands.Bot(command_prefix='.', intents=discord.Intents.none())

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(choice(["osu!","osu!Lazer", "osu!stream"])))
    print("Discord bot is up")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

# command for discord to request the scorepost from last play

@bot.tree.command(name="scorepost", description="This command will generate a scorepost title you can use in /r/osugame from an user's last play")
@app_commands.describe(osu_user="The username of the player you want to generate a scorepost title", mode="The gamemode of the player who set the play, defaults to osu!")
@app_commands.rename(osu_user="username", mode="gamemode")
@app_commands.Argument.required(False)
async def scoreposter(interaction: discord.Interaction, osu_user : str, mode : Literal['osu!std','osu!mania','osu!taiko','osu!catch'] = 'osu!std'):
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(choice(["osu!","osu!Lazer", "osu!stream"])))
    await interaction.response.send_message(f"```{scorepost(osu_user ,mode)}```", ephemeral=False)


# # command for discord to request scorepost from link

# @bot.tree.command(name="scorepost-link", description="This command will generate a scorepost title you can use in /r/osugame from a score link")
# @app_commands.describe(score_link="The link of the score you want to generate a scorepost title")
# @app_commands.rename(score_link="score-link")
# async def scoreposter(interaction: discord.Interaction, score_link : str):
#     await interaction.response.send_message(f"{scorepost(score_link, True)}", ephemeral=False)
    

bot.run(discord_token)

    # #regex to check if it's a score link

    # elif link and re.search("https://osu\.ppy\.sh/scores/[a-zA-Z]+//([1-9][0-9]*)|0/", username):
    #     try:
    #         print(f"making initial score request for {username}...")
    #         inital_response_user = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={osu_api_key}&u={username}&m={gamemode}&limit=1")
    #     except:
    #         return "No plays done by that player recently"
    #     else:
    #         # parse the response as JSON
    #         initial_data = inital_response_user.json()
    #         beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods, score_id = extract_initial_data(initial_data)
    #     accuracy = min(100.0 * ((n300 * 300.0) + (n100 * 100.0) + (n50 * 50.0)) / ((n300 + n100 + n50 + nmiss) * 300.0), 100)
    
    # elif link and re.search("https://osu\.ppy\.sh/scores/[a-zA-Z]+//([1-9][0-9]*)|0/", username) == False:
    #     return "Not an osu! score link"