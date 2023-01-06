import requests
import os
from random import choice
from typing import List, Literal

from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from PIL import Image
import geckodriver_autoinstaller

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

# check that the keys are present in the configuration file
if not osu_api_key or not discord_token:
    print("You must specify both the osu API key and the Discord bot token in the configuration file!")
    raise LookupError

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
        beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id = (
            initial_data[0]["beatmap_id"],
            int(initial_data[0]["maxcombo"]), 
            int(initial_data[0]["count300"]), 
            int(initial_data[0]["count100"]), 
            int(initial_data[0]["count50"]), 
            int(initial_data[0]["countmiss"]), 
            int_to_santised_int(int(initial_data[0]["enabled_mods"])),
            initial_data[0]["score_id"]
        )
    except IndexError as e:
        print(f"an exception occurred: '{e}'; that user probably doesn't have any data available.")
        raise
    return beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id

def extract_map_data(map_data):
    artist, title, creator, diff, map_max, mode, status = (
        map_data[0]["artist"],
        map_data[0]["title"],
        map_data[0]["creator"],
        map_data[0]["version"],
        int(map_data[0]["max_combo"]),
        int(map_data[0]["mode"]),
        int(map_data[0]["approved"])
    )
    return artist, title, creator, diff, map_max, mode, status

def mode_to_string(mode):
    modes = {
        0: "osu!",
        1: "osu!taiko",
        2: "osu!catch",
        3: "osu!mania"
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

def take_screenshot(url, crop_coordinates):
    # install geckodriver
    geckodriver_autoinstaller.install()

    # start a web browser and navigate to the webpage
    opts = FirefoxOptions()
    opts.add_argument("--headless")
    driver = webdriver.Firefox(options=opts)
    driver.get(url)

    # tell user we're waiting for their screenshot
    print("waiting for screenshot...")
    # wait for the page to fully load
    WebDriverWait(driver, 10)  # wait for up to 10 seconds

    # take a screenshot of the webpage 
    screenshot = driver.get_screenshot_as_png()
    # save the screenshot to a file
    with open("screenshot.png", "wb") as f:
        f.write(screenshot)

    # close the web browser
    driver.quit()

    # open the screenshot
    screenshot = Image.open("screenshot.png")
    # crop the image
    cropped_screenshot = screenshot.crop(crop_coordinates)
    # save the cropped image
    cropped_screenshot.save("ss.png")

    if os.path.exists("screenshot.png"):
        # get rid of the unneeded full screenshot
        os.remove("screenshot.png")
        print("screenshot made!")
    else:
        print("this file doesn't exist, but wasn't deleted by us..")
        raise FileNotFoundError

def getScoreLink(score_id, gamemode):
    if score_id == None:
        return None

    # map the gamemode values to URL strings
    mode_mapping = {
        0: "osu",
        1: "taiko",
        2: "fruits",
        3: "mania"
    }
    
    # look up the URL string for the given gamemode
    mode_string = mode_mapping.get(gamemode, "osu")
    return f"**Score link:** https://osu.ppy.sh/scores/{mode_string}/{score_id}"

def scorepost(username: str, ruleset: str):
    # map mode to numbers
    gamemode = string_to_mode(ruleset)

    # make a request to the osu! API to retrieve the user's most recent play
    print(f"making initial score request for {username}...")
    initial_response_user = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={osu_api_key}&u={username}&m={gamemode}&limit=1")

    # parse the response as JSON
    initial_data = initial_response_user.json()

    # if initial_data returns an empty dictionary, then that user doesn't have any data
    if initial_data == []:
        return f"No plays done by {username} on {ruleset} recently"

    # make the score_id global
    global score_id

    # extract the relevant information from the response
    beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id = extract_initial_data(initial_data)

    # convert the integer mods to a readable string
    readable_mods = int_to_readable(int(int_mods))

    print("done!")
    print("making the score's map request...")

    map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={osu_api_key}&b={beatmap_id}&limit=1")
    map_data = map_response.json()
    artist, title, creator, diff, map_max, mode, status = extract_map_data(map_data)

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

    # get map status

    # Map the status values to strings
    status_mapping = {
        -2: "if ranked",
        -1: "if ranked",
        0: "if ranked",
        1: "if submitted",
        2: "if submitted",
        3: "if ranked",
        4: "if ranked"
    }

    # check if score_id is not None
    if score_id is not None:
        # assign a value to beatmap_status based on the status value
        beatmap_status = status_mapping.get(status, "")
    else:
        # set beatmap_status to an empty string if score_id is None
        beatmap_status = ""

    scorepost = f"{f'[{mode_to_string(gamemode)}] ' if int(gamemode) != 0 else ''}{username} | {artist} - {title} [{diff}] ({creator}, {sr}⭐️){mods} {accuracy:.2f}% {combo}{miss_string}| {round(pp.pp):,}pp {max_pp_string} {beatmap_status} ".replace("%20", " ").replace("HDDTNC", "HDNC")

    global link
    link = getScoreLink(score_id, gamemode)

    return scorepost

# start discord bot
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.none()
        super().__init__(command_prefix=commands.when_mentioned_or('.'), intents=intents)

    async def on_ready(self):
        await bot.change_presence(status=discord.Status.online, activity=discord.Game(choice(["osu!","osu!Lazer", "osu!stream"])))
        print("Discord bot is up")
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(e)

bot = Bot()

# command for discord to request the scorepost from last play
@bot.tree.command(name="scorepost", description="This command will generate a scorepost title you can use in /r/osugame from an user's last play")
@app_commands.describe(osu_user="The username of the player you want to generate a scorepost title", mode="The gamemode of the player who set the play, defaults to osu!")
@app_commands.rename(osu_user="username", mode="gamemode")
async def scoreposter(interaction: discord.Interaction, osu_user: str, mode: Literal['osu!std','osu!mania','osu!taiko','osu!catch']):
    # Get information from the function
    title = scorepost(osu_user, mode)
    # view = SS()
    bot.ruleset = mode
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(choice(["osu!","osu!Lazer", "osu!stream"])))
    if link != None:
        # await interaction.response.send_message(f"```{title}``` {link}", ephemeral=False, view=view)
        await interaction.response.send_message(f"```{title}``` {link}", ephemeral=False)
    else:
        await interaction.response.send_message(f"```{title}```", ephemeral=False)

class SS(discord.ui.View):
    def __init__(self):
        super().__init__()

    # @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    @discord.ui.button(label="Get screenshot", emoji="🖼️", style=discord.ButtonStyle.gray)
    async def scorepost_picture(self, interaction: discord.Interaction, button: discord.ui.Button):
        take_screenshot(f"https://osu.ppy.sh/scores/{mode_to_url_string(int(string_to_mode(bot.ruleset)))}/{score_id}", (175, 95, 1180, 640))
        await interaction.response.send_message(file=discord.File('./ss.png'), ephemeral=False)
        self.stop()


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
    # !score_link && !approved -> unranked
    # !score_link && approved -> ranked / loved / qualified && failed / better old score
    # score_link && approved -> ranked / loved / qualified

    # 4 = loved, 3 = qualified, 2 = approved, 1 = ranked, 0 = pending, -1 = WIP, -2 = graveyard
