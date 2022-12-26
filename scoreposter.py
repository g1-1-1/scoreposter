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
    if value == 0:
        return []
    else:
        return [name for mod, name in mods if value & mod]

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
beatmap_id, score_max, n300, n100, n50, nmiss, perfect, int_mods = (
    initial_data[0]["beatmap_id"], 
    initial_data[0]["maxcombo"], 
    int(initial_data[0]["count300"]), 
    int(initial_data[0]["count100"]), 
    int(initial_data[0]["count100"]), 
    int(initial_data[0]["countmiss"]), 
    initial_data[0]["perfect"], 
    int(initial_data[0]["enabled_mods"])
)
accuracy = (n300 + n100 + n50 / 2) / (n300 + n100 + n50 + nmiss)
formatted_accuracy = format(accuracy, '.2f')
readable_mods = int_to_readable(int(int_mods))

print("made!")

print("making the score's map request...")
map_response = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={api_key}&b={beatmap_id}&limit=1")
map_data = map_response.json()

artist, title, creator, diff, sr, map_max = (
    map_data[0]["artist"],
    map_data[0]["title"],
    map_data[0]["creator"],
    map_data[0]["version"],
    round(float(map_data[0]["difficultyrating"]), 2),
    map_data[0]["max_combo"],
)

print("made!")
print("creating the scorepost...")

mods = "" if int_mods == 0 else " +" + ''.join(readable_mods)

get_osu_file = requests.get(f"https://old.ppy.sh/osu/{beatmap_id}", stream=True)

with open("beatmap.osu", "wb") as f:
    for chunk in get_osu_file.iter_content(chunk_size=8192):
        f.write(chunk)

map = Beatmap(bytes=open("beatmap.osu", "rb").read())
calc = Calculator(mode=0, mods=int(int_mods))
calc.set_acc(int(accuracy))
calc.set_n300(n300)
calc.set_n100(n100)
calc.set_n50(n50)
calc.set_n_misses(nmiss)
calc.set_combo(int(score_max))

pp = calc.performance(map)

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

scorepost = f"{args.username} | {artist} - {title} [{diff}] (mapped by {creator}, {sr}*){mods} {formatted_accuracy}% {combo}{miss_string}{round(pp.pp)}pp {max_pp_string} "

# print the scorepost to the console
print(f"\n{scorepost}")
print("\ncompleted!")
