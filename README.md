# scoreposter
a python script that generates /r/osugame scorepost titles and screenshots of score pages.


## how to use
1. [install git](https://git-scm.com/)
2. clone this repo (e.g. `git clone https://github.com/0i8/scoreposter.git`)
3. [get your api key](https://osu.ppy.sh/p/api)
4. put your api key in .env
5. [install python](https://www.python.org/downloads/)
6. open your console where you have this repository in
7. run `pip install -r requirements.txt`
8. to use the screenshot function, (on linux), run `sudo apt install firefox-geckodriver` and set the screenshots variable in .env to "yes"
9. if everything is successful, in your console, run `python scoreposter.py -u=[username]`

for example, if you want to grab mrekk's last play:
![example](https://file.coffee/u/L0sQOp1AJEE7gGFaa7rjn.png)

and to grab dressurf's (osu!mania player) last play:
![example2](https://file.coffee/u/rU1Y3AugqeCLuVO0aV90V.png)

please report any bugs in the issues tab

do whatever you want with the code

if you have meaningful changes open a PR

thanks
