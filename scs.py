#!/usr/bin/python3
import pathlib, json, os
from typing_extensions import Self
from urllib.request import Request, urlopen
from html_table_parser import HTMLTableParser
from datetime import date
__location__ = pathlib.Path(__file__).parent.resolve()
__results__ = __location__ / "Results"

class Config:
    def __init__(self: Self, file_name: str = "config"):
        with open(__location__ / f"{file_name}.json", 'r', encoding="utf-8", newline='') as r_json:
            data = json.loads(r_json.read())
        self.steam_login_secure = data["steamLoginSecure"]
        self.game_whitelist = data["gameWhiteList"]

def fetch_table(cfg: Config, url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Cookie": f"steamLoginSecure={cfg.steam_login_secure}"})
    web = urlopen(req).read().decode("utf-8")
    parsed_html = HTMLTableParser()
    parsed_html.feed(web)

    return parsed_html.tables[0][1:]

def main(args: list[str]) -> bool:
    if not os.path.exists(__results__):
        __results__.mkdir(parents=True, exist_ok=True)

    current_dir = __results__ / date.today().strftime("%y%m%d")
    if not os.path.exists(current_dir):
        current_dir.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    remote_table = fetch_table(cfg, "https://store.steampowered.com/account/remotestorage")
    if len(cfg.game_whitelist) > 0:
        remote_table = list(filter(lambda x: x[0] in cfg.game_whitelist, remote_table))

    for game_row in remote_table:
        download_tbl = fetch_table(cfg, game_row[3])
        game_dir = current_dir / game_row[0].replace(":", "").replace("!", "").replace("?", "")
        if not os.path.exists(game_dir):
            game_dir.mkdir(parents=True, exist_ok=True)

        for download_row in list(filter(lambda x: len(x[1]) > 0, download_tbl)):
            full_name = (f"%{download_row[0]}%{download_row[1]}" if len(download_row[0]) > 0 else download_row[1]).replace("/", "%").replace("\\", "%")
            req = Request(download_row[4], headers={"User-Agent": "Mozilla/5.0", "Cookie": f"steamLoginSecure={cfg.steam_login_secure}"})
            data = urlopen(req).read()
            with open(game_dir / full_name, 'wb') as w_data:
                w_data.write(data)

        print(f"Downloaded files for: {game_row[0]}")

    return False

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])