import os
import json
import asyncio
import aiohttp
import aiofiles
import requests
from bs4 import BeautifulSoup
import time

SOUNDS_JS = "sounds.js"
SPLITTER = "// SPLITTER ---------------"
BASE_URL = "https://www.myinstants.com/en/index/us/?page={}"
START_PAGE = 1
END_PAGE = 100
SCRAPE_DELAY = 0.3

def scrape_pages():
    sounds = []
    seen = set()

    for page in range(START_PAGE, END_PAGE + 1):
        url = BASE_URL.format(page)
        print(f"[SCRAPE] Page {page}")

        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        instants = soup.select("#instants_container .instant")

        if not instants:
            break

        for el in instants:
            btn = el.select_one("button[onclick^='play']")
            if not btn:
                continue

            mp3 = btn["onclick"].split("'")[1]
            if mp3 in seen:
                continue
            seen.add(mp3)

            name_el = el.select_one(".instant-link")
            circle_el = el.select_one(".circle")

            sounds.append({
                "name": name_el.text.strip() if name_el else None,
                "color": (
                    circle_el["style"].split(":")[-1].strip()
                    if circle_el and "style" in circle_el.attrs
                    else None
                ),
                "mp3": mp3
            })

        time.sleep(SCRAPE_DELAY)

    print(f"[SCRAPE] Collected {len(sounds)} sounds")
    return sounds

def load_sounds_js():
    with open(SOUNDS_JS, "r", encoding="utf-8") as f:
        content = f.read()

    before, after = content.split(SPLITTER, 1)
    data = json.loads(after.strip())
    return before, data

def write_sounds_js(prefix, sounds):
    with open(SOUNDS_JS, "w", encoding="utf-8") as f:
        f.write(prefix)
        f.write(SPLITTER + "\n")
        json.dump(sounds, f, indent=4)

def merge_sounds(old, new):
    old_map = {s["mp3"]: s for s in old}
    new_map = {s["mp3"]: s for s in new}

    kept = []
    removed = []

    for mp3, sound in old_map.items():
        if mp3 in new_map:
            kept.append(new_map[mp3])
        else:
            removed.append(sound)

    for mp3, sound in new_map.items():
        if mp3 not in old_map:
            kept.append(sound)

    return kept + removed

async def download_sound(session, sound):
    url = "https://www.myinstants.com" + sound["mp3"]
    filename = os.path.basename(sound["mp3"])
    save_path = os.path.join("media", "sounds", filename)

    if os.path.exists(save_path):
        return

    async with session.get(url) as response:
        if response.status == 200:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            async with aiofiles.open(save_path, "wb") as f:
                await f.write(await response.read())
            print(f"[DL] {filename}")

async def main():
    scraped = scrape_pages()
    prefix, old_sounds = load_sounds_js()
    merged = merge_sounds(old_sounds, scraped)
    write_sounds_js(prefix, merged)

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*(download_sound(session, s) for s in merged))

if __name__ == "__main__":
    asyncio.run(main())
