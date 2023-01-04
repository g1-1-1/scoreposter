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

def calculate_accuracy(perfect_count, hundred_count, fifty_count, misses):
    accuracy = (perfect_count * 300 + hundred_count * 100 + fifty_count * 50) / (perfect_count + fifty_count + hundred_count + misses) / 300 * 100
    return accuracy


# define command line arguments using the argparse module
parser = argparse.ArgumentParser()
parser.add_argument("-u", "--username", required=True, help="the username of the user whose play you want to retrieve.")
args = parser.parse_args()

api_key = os.getenv("api_key")

# make a request to the osu! API to retrieve the user's most recent play
inital_response = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={api_key}&u={args.username}&limit=1")
print("making initial score request...")

# parse the response as JSON
initial_data = inital_response.json()

# extract the relevant information from the response
beatmap_id, rank, score_max, n300, n100, n50, nmiss, perfect, int_mods = (
    initial_data[0]["beatmap_id"], 
    initial_data[0]["rank"], 
    int(initial_data[0]["maxcombo"]), 
    int(initial_data[0]["count300"]), 
    int(initial_data[0]["count100"]), 
    int(initial_data[0]["count50"]), 
    int(initial_data[0]["countmiss"]), 
    initial_data[0]["perfect"], 
    int_to_santised_int(int(initial_data[0]["enabled_mods"]))
)

readable_mods = int_to_readable(int(int_mods))

print("made!")

print("making the score's map request...")
map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={api_key}&b={beatmap_id}&limit=1")
map_data = map_response.json()

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

total_objects = circles + sliders + spinners
print(total_objects)
accuracy = min(100.0 * ((n300 * 300.0) + (n100 * 100.0) + (n50 * 50.0)) / ((n300 + n100 + n50 + nmiss) * 300.0), 100)

print("made!")
print("creating the scorepost...")

mods = "" if int_mods == 0 else " +" + ''.join(readable_mods)

get_osu_file = requests.get(f"https://old.ppy.sh/osu/{beatmap_id}", stream=True)

with open("beatmap.osu", "wb") as f:
    for chunk in get_osu_file.iter_content(chunk_size=8192):
        f.write(chunk)

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
else:
    miss_string = f" {nmiss}❌ "
    combo = f"{int(score_max):,}x/{int(map_max):,}x"
    calc.set_n_misses(0)
    calc.set_combo(int(map_max))
    calc.set_mods(int_mods)
    max_pp = calc.performance(map)
    max_pp_string = f"({round(max_pp.pp):,}pp if FC)"

print()

scorepost = f"{args.username} | {artist} - {title} [{diff}] (mapped by {creator}, {sr}⭐️){mods} {accuracy:.2f}% {combo}{miss_string}{round(pp.pp):,}pp {max_pp_string} ".replace("%20", " ").replace("HDDTNC", "HDNC")

# print the scorepost to the console
print(f"{scorepost}")
print("\ncompleted!")
