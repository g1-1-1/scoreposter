import argparse
import requests
import os
from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from circleguard import Circleguard
from circleguard import ReplayString
from PIL import Image
from typing import List
from rosu_pp_py import Beatmap, Calculator
from dotenv import load_dotenv

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

def needs_conversion(value: int) -> bool:
    if value == 0:
        return False
    else:
        mods_to_check = [512, 256, 64, 16] # NC, HT, DT, HR, EZ
        combined_value = 0
        for mod in mods_to_check:
            if value & mod:
                combined_value |= mod
        return True

def extract_initial_data(initial_data):
    try:
        beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id, user_id = (
            initial_data[0]["beatmap_id"], 
            int(initial_data[0]["maxcombo"]), 
            int(initial_data[0]["count300"]), 
            int(initial_data[0]["count100"]), 
            int(initial_data[0]["count50"]), 
            int(initial_data[0]["countmiss"]), 
            int_to_santised_int(int(initial_data[0]["enabled_mods"])),
            initial_data[0]["score_id"],
            initial_data[0]["user_id"]
        )
    except IndexError as e:
        print(f"an exception occurred: '{e}'; that user probably doesn't have any data available.")
        raise

    return beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id, user_id

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
    return modes.get(mode, int(args.mode))

def mode_to_url_string(mode):
    modes = {
        0: "osu",
        1: "taiko",
        2: "fruits",
        3: "mania"
    }
    return modes.get(mode, int(args.mode))

def take_screenshot(url, crop_coordinates):
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

# define command line arguments using the argparse module
parser = argparse.ArgumentParser()
parser.add_argument("-u", "--username", required=True, help="the username of the user whose play you want to retrieve.")
parser.add_argument("-m", "--mode", required=False, default=os.getenv("default_mode"), help="the mode where the play happened, default is osu! standard (0); and syntax is numeric (0 = osu, 1 = taiko, 2 = fruits, 3 = mania)")
parser.add_argument("-l", "--limit", required=False, default=1, help="amount of scoreposts you want, default is 1")
args = parser.parse_args()

# assign api_key .env variable to a global variable so that we don't have to call getenv() every time
api_key = os.getenv("api_key")

if int(args.mode) not in (0, 1, 2, 3):
    print("passed mode is invalid! exiting...")
    raise ValueError

# tell the user we're about to make the initial request
print("making initial score request...")
# make a request to the osu! API to retrieve the user's most recent play
initial_response = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={api_key}&u={args.username}&m={int(args.mode)}&limit=1")
# parse the response as JSON
initial_data = initial_response.json()
# extract using function and assign tuple to variables
beatmap_id, score_max, n300, n100, n50, nmiss, int_mods, score_id, user_id = extract_initial_data(initial_data)
# tell user we've finished that request
print("made!")

# then tell them we're moving to the next required request
print("making the score's map request...")
map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={api_key}&b={beatmap_id}&limit=1")
map_data = map_response.json()
artist, title, creator, diff, map_max, mode, status = extract_map_data(map_data)
print("made!")

# now we're going to announce we're grabbing replay data
print("attempting to grab replay..")
# and grab replay data
circleguard = Circleguard(api_key)
try:
    replay = circleguard.ReplayMap(beatmap_id, user_id)
    if int(status) not in (-2, -1, 0, 3, 4):
        if needs_conversion(int_mods) is True:
            replay_ur = f"{round(circleguard.ur(replay, cv=True), 2)} cv. UR "
            print("made!")
        else:
            replay_ur = f"{round(circleguard.ur(replay, cv=True), 2)} UR "
            print("made!")
    else:
        replay_ur = ""
        print("made, however the score cannot be calculated for UR; so it is empty.")
except Exception as e:
    print(f"couldn't find replay! skipping UR calculation... {e}")
    replay_ur = ""

# tell the user we're now going to create the scorepost (all we really have to do left is calculate pp)
print("creating the scorepost...")
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
calc.set_n300(n300)
calc.set_n100(n100)
calc.set_n50(n50)
calc.set_mods(int_mods)
calc.set_n_misses(nmiss)
calc.set_combo(score_max)

pp = calc.performance(map)
sr = round(float(pp.difficulty.stars), 2)

if score_max - 20 <= map_max and nmiss == 0:
    combo = "FC "
    max_pp_string = ""
    miss_string = ""
else:
    if nmiss == 0:
        combo = f"{int(score_max):,}x/{int(map_max):,}x "
        calc.set_n_misses(0)
        calc.set_combo(int(map_max))
        calc.set_n300(n300)
        calc.set_n100(n100)
        calc.set_n50(n50)
        calc.set_mods(int_mods)
        max_pp = calc.performance(map)
        max_pp_string = f"({round(max_pp.pp):,}pp if FC)"
        miss_string = ""
    else:
        miss_string = f" {nmiss}❌ "
        combo = f"{int(score_max):,}x/{int(map_max):,}x"
        calc.set_n_misses(0)
        calc.set_combo(int(map_max))
        calc.set_mods(int_mods)
        max_pp = calc.performance(map)
        max_pp_string = f"({round(max_pp.pp):,}pp if FC)"

# map the status values to strings
status_mapping = {
    -2: "if ranked ",
    -1: "if ranked ",
    0: "if ranked ",
    1: "if submitted ",
    2: "if submitted ",
    3: "if ranked ",
    4: "if ranked "
}

# check if score_id is None
if score_id is None or int(status) in (-2, -1, 0, 3, 4):
    # assign a value to beatmap_status based on the status value
    if_status = status_mapping.get(status, "")
else:
    # set beatmap_status to an empty string if score_id is None
    if_status = ""

scorepost = (
    f"{f'({mode_to_string(int(args.mode))}) ' if int(args.mode) != 0 else ''}"
    f"{args.username} | {artist} - {title} [{diff}] (mapped by {creator}, {sr}⭐️){mods} "
    f"{accuracy:.2f}% {combo}{miss_string}{replay_ur}| {round(pp.pp):,}pp {if_status}{max_pp_string}"
).replace("%20", " ")

# print the scorepost to the console
print(f"\n{scorepost}")

if score_id is not None:
    print(f"\nhere's the score link, on osu!: https://osu.ppy.sh/scores/{mode_to_url_string(int(args.mode))}/{score_id}")
    if os.getenv("screenshots") == "yes":
        take_screenshot(f"https://osu.ppy.sh/scores/{mode_to_url_string(int(args.mode))}/{score_id}", (175, 95, 1180, 640))
        print(f"\nsince we have a score link and you have screenshots enabled, we have saved a snapshot of the page as 'ss.png'.")
else:
    print(f"\nsince this play is a failed one, not their best score, or unranked; a score link is not available!")

print("completed!")
