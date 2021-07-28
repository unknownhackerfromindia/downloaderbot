import re
import os
import asyncio
import logging
from functools import wraps
from subprocess import getstatusoutput
from config import Config
from pyrogram.types.messages_and_media import message
from telegram_upload import files
from pyrogram import Client
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup

API_ID = int(os.environ.get("API_ID", Config.API_ID))
API_HASH = os.environ.get("API_HASH", Config.API_HASH)
BOT_TOKEN = os.environ.get("BOT_TOKEN", Config.BOT_TOKEN)

bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

with bot:
    BOT = bot.get_me().username.lower()

auth_users = list(eval(os.environ.get("AUTH_USERS", Config.AUTH_USERS)))
sudo_groups = list(eval(os.environ.get("GROUPS", Config.GROUPS)))
sudo_html_groups = list(eval(os.environ.get("HTML_GROUPS", Config.HTML_GROUPS)))
sudo_users = auth_users


logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s:%(levelname)s %(message)s",
    filemode="w",
    level=logging.WARNING,
)

logger = logging.getLogger()


def exception(logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            try:
                return func(*args, **kwargs)
            except:
                issue = "Exception in " + func.__name__ + "\n"
                issue = (
                    issue
                    + "-------------------------\
                ------------------------------------------------\n"
                )
                logger.exception(issue)

        return wrapper

    return decorator


async def query_same_user_filter_func(_, __, query):
    message = query.message.reply_to_message
    if query.from_user.id != message.from_user.id:
        await query.answer("❌ Not for you", True)
        return False
    else:
        return True


query_same_user = filters.create(query_same_user_filter_func)
query_document = filters.create(
    lambda _, __, query: query.message.reply_to_message.document
)


@bot.on_message(filters.command("start"))
async def start(bot, message):
    await message.reply("Send video link or html")


async def send_video(message, path, caption, quote, filename):
    atr = files.get_file_attributes(path)
    duration = atr[0].duration
    width = atr[0].w
    height = atr[0].h
    thumb = "thumb.png"
    await message.reply_video(
        video=path,
        caption=caption,
        duration=duration,
        width=width,
        height=height,
        thumb=thumb,
        supports_streaming=True,
        quote=quote,
        # file_name=filename
    )

def parse_html(file, def_format):
    with open(file, "r") as f:
        source = f.read()

    soup = BeautifulSoup(source, "html.parser")

    all_videos_soup = soup.select_one("div#videos")
    topics_soup = all_videos_soup.select("div.topic")
    videos = []
    for topic_soup in  topics_soup:
        topic_name = topic_soup.select_one("span.topic_name").get_text(strip=True)
        videos_soup = topic_soup.select("p.video")
        for video_soup in videos_soup:
            video_name = video_soup.select_one("span.video_name").get_text(strip=True)
            video_link = video_soup.select_one("a").get_text(strip=True)
            if not (video_link.startswith("http://") or video_link.startswith("https://")):
                    continue
            elif 'google' in video_link:
                continue
            videos.append((video_link, def_format, video_name, topic_name, False))

    return videos


@bot.on_callback_query(query_document & query_same_user)
async def choose_html_video_format(bot, query):
    message = query.message.reply_to_message
    def_format = query.data
    if message.document["mime_type"] != "text/html":
        return
    file = f"./downloads/{message.chat.id}/{message.document.file_unique_id}.html"
    await message.download(file)

    videos = parse_html(file, def_format)
    await message.reply("Downloading!!!")
    await download_videos(message, videos)


@bot.on_message(
    (
        (filters.command("download_link") & ~ filters.group)
        | filters.regex(f"^/download_link@{BOT}")
    )
    & (filters.chat(sudo_html_groups) | filters.user(sudo_users))
    & filters.document
    )
async def download_html(bot, message):
    if message.document["mime_type"] != "text/html":
        return
    file = f"./downloads/{message.chat.id}/{message.document.file_unique_id}.html"
    msg = await message.download(file)

    with open(file, "r") as f:
        source = f.read()

    soup = BeautifulSoup(source, "html.parser")

    info = soup.select_one("p#info")
    if info is not None:
        title = soup.select_one("h1#batch").get_text(strip=True)

    formats = ["144", "240", "360", "480", "720"]
    buttons = []
    for format in formats:
        buttons.append(InlineKeyboardButton(text=format + "p", callback_data=format))
    buttons_markup = InlineKeyboardMarkup([buttons])

    await message.reply(title, quote=True, reply_markup=buttons_markup)
    os.remove(file)


# @bot.on_callback_query()
# async def upload(bot, query):
# message = query.message.reply_to_message
# format = query.data
# file = (
# "./downloads/"
# + str(message.from_user.id)
# + "/"
# + message.document.file_id
# + ".html"
# )
# await message.download(file)

# with open(file, "r") as f:
# source = f.read()

# soup = BeautifulSoup(source, "html.parser")

# vids = "".join(
# [
# str(tag)
# for tag in soup.find_all("p", style="text-align:center;font-size:25px;")
# ]
# )
# vids_soup = BeautifulSoup(vids, "html.parser")
# links = [link.extract().text for link in vids_soup.findAll("a")]
# name = re.compile("\d+\..*?(?=<br/>)")
# names = name.findall(vids)
# vids_dict = dict(zip(names, links))

# for vid in vids_dict:
# vid_name = vid + ".mp4"
# vid_path = "./downloads/" + str(message.from_user.id) + "/" + vid_name
# vid_link = vids_dict[vid]
# command = (
# "youtube-dl -o '"
# + vid_path
# + "' -f 'bestvideo[height="+format+"]+bestaudio' "
# + vid_link
# )
# os.system(command)
# await message.reply_chat_action("upload_video")
# await send_video(message, vid_path, vid)
# os.remove(vid_path)


def download_video(message, video):
    chat = message.chat.id
    link = video[0]
    vid_format = video[1]
    title = video[2]
    topic = video[3]
    quote = video[4]

    if not vid_format.isnumeric():
        title = vid_format

    if "youtu" in link:
        if vid_format in ["144", "240", "480"]:
            ytf = f"'bestvideo[height<={vid_format}][ext=mp4]+bestaudio[ext=m4a]'"
        elif vid_format == "360":
            ytf = 18
        elif vid_format == "720":
            ytf = 22
        else:
            ytf = 18
    elif ("deshdeepak" in link and len(link.split("/")[-1]) == 13) or (
        "magnetoscript" in link
        and ("brightcove" in link or len(link.split("/")[-1]) == 13)
    ):
        if vid_format not in ["144", "240", "360", "480", "720"]:
            vid_format = "360"
        ytf = f"'bestvideo[height<={vid_format}]+bestaudio'"
    elif ("deshdeepak" in link and len(link.split("/")[-1]) == 8) or (
        "magnetoscript" in link and "jwp" in link
    ) or "jwplayer" in link:
        if vid_format == "144":
            vid_format = "180"
        elif vid_format == "240":
            vid_format = "270"
        elif vid_format == "360":
            vid_format = "360"
        elif vid_format == "480":
            vid_format = "540"
        elif vid_format == "720":
            vid_format = "720"
        else:
            vid_format = "360"
        ytf = f"'best[height<={vid_format}]'"
        if '.mp4' in link:
            ytf = "'best'"
        elif '.m3u8' in link:
            ytf = "'best'"
    else:
        ytf = "'best'"

    cmd = (
        f"yt-dlp -o './downloads/{chat}/%(id)s.%(ext)s' -f {ytf} --no-warning '{link}'"
    )
    filename = title.replace('/','|').replace('+','_').replace('?',':Q:').replace('*',':S:').replace('#',':H:')
    filename_cmd = f"{cmd} -e --get-filename -R 25"
    st1, out1 = getstatusoutput(filename_cmd)
    if st1 != 0:
        caption = f"Can't Download. Probably DRM.\n\nLink: {link}\n\nTitle: {title}\n\nError: {out1}"
        return 1, "", caption, quote, filename
    yt_title, path = out1.split("\n")
    if title == "":
        title = yt_title

    download_cmd = f"{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args 'aria2c: -x 16 -j 32'"
    st2, out2 = getstatusoutput(download_cmd)
    if st2 != 0:
        caption = f"Can't download link.\n\nLink: {link}\n\nTitle: {title}\n\nError: {out2}"
        return 2, "", caption, quote, filename
    else:
        filename += '.' + path.split('.')[-1]
        caption = f"Link: {link}\n\nTitle: {title}\n\nTopic: {topic}"
        return 0, path, caption, quote, filename


# @exception(logger)
async def download_videos(message, videos):
    for video in videos:
        r, path, caption, quote, filename = download_video(message, video)
        if r in [1, 2]:
            await message.reply(caption, quote=quote)
        elif r == 0:
            await send_video(message, path, caption, quote, filename)
            os.remove(path)


def get_videos(req_videos, def_format):
    videos = []
    for video in req_videos:
        video_parts = video.split("|")
        video_link = video_parts[0]
        video_format = (
            video_parts[1]
            if len(video_parts) == 2 and video_parts[1] != ""
            else def_format
        )
        videos.append((video_link, video_format, "", "", True))

    return videos


@bot.on_callback_query(~query_document & query_same_user)
async def choose_video_format(bot, query):
    message = query.message.reply_to_message
    def_format = query.data
    commands = message.text.split()
    req_videos = commands[1:-1]
    videos = get_videos(req_videos, def_format)
    await message.reply("Downloading!!!")
    await download_videos(message, videos)


@bot.on_message(
    (
        (filters.command("download_link") & ~ filters.group)
        | filters.regex(f"^/download_link@{BOT}")
    )
    & (filters.chat(sudo_groups) | filters.user(sudo_users))
)
async def download_link(bot, message):
    user = message.from_user.id
    commands = message.text.split()
    if len(commands) == 1:
        await message.reply(
            "Send video link(s) separated by space, and format separated by | or f at end to choose format (optional) \n\n"
            + "e.g. /downloadLink https://link1|360 http://link2 http://link3|480 \n"
            + "e.g. /downloadLink http://link1 http://link2 f\n\n"
            + "Default format 360p if unspecified.\n"
            + "One link per user at a time."
        )
        return
    if commands[-1] == "f":
        if user not in sudo_users and len(commands) > 3:
            await message.reply("Not authorized for this action.", quote=True)
            return
        formats = ["144", "240", "360", "480", "720"]
        buttons = []
        for def_format in formats:
            buttons.append(
                InlineKeyboardButton(text=def_format + "p", callback_data=def_format)
            )
        buttons_markup = InlineKeyboardMarkup([buttons])
        await message.reply("Choose Format", quote=True, reply_markup=buttons_markup)
    else:
        if user not in sudo_users and len(commands) > 2:
            await message.reply("Not authorized for this action.", quote=True)
            return
        def_format = "360"
        req_videos = commands[1:]
        videos = get_videos(req_videos, def_format)
        await message.reply("Downloading!!!")
        await download_videos(message, videos)


bot.run()
