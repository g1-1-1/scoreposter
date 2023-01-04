import argparse
import requests
import os
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
    return modes.get(mode, "invalid mode passed!")

def mode_to_url_string(mode):
    modes = {
        0: "osu",
        1: "taiko",
        2: "fruits",
        3: "mania"
    }
    return modes.get(mode, "invalid mode passed!")

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
beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods, score_id = extract_initial_data(initial_data)

# tell user we've finished that request
print("made!")
# then tell them we're moving to the next required request
print("making the score's map request...")

map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={api_key}&b={beatmap_id}&limit=1")
map_data = map_response.json()
artist, title, creator, diff, map_max, circles, sliders, spinners, mode = extract_map_data(map_data)

print("made!")
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
    combo = f"{int(score_max):,}x/{int(map_max):,}x"
    calc.set_n_misses(0)
    calc.set_combo(int(map_max))
    calc.set_mods(int_mods)
    max_pp = calc.performance(map)
    max_pp_string = f"({round(max_pp.pp):,}pp if FC)"

scorepost = f"{f'({mode_to_string(int(args.mode))}) ' if int(args.mode) != 0 else ''}{args.username} | {artist} - {title} [{diff}] (mapped by {creator}, {sr}⭐️){mods} {accuracy:.2f}% {combo}{miss_string}{round(pp.pp):,}pp {max_pp_string} ".replace("%20", " ").replace("HDDTNC", "HDNC")

# print the scorepost to the console
print(f"\n{scorepost}")

if score_id != None:
    print(f"\nhere's the score link, on osu!: https://osu.ppy.sh/score/{mode_to_url_string(int(args.mode))}/{score_id}")
else:
    print(f"\nsince this play is a failed one, a score link is not available!")
    
print("completed!")
