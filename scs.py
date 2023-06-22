#!/usr/bin/python3
import pathlib
import json
import asyncio
import urllib.request
import urllib.parse
import re
import datetime
import base64
from http.client import HTTPResponse
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from typing_extensions import Self
from html_table_parser import HTMLTableParser
__location__ = pathlib.Path(__file__).parent.resolve()

class Config:
    def __init__(self: Self, file_name: str = "config"):
        with open(__location__ / f"{file_name}.json", 'r', encoding="utf-8", newline='') as r_json:
            data: dict[str, str] = json.loads(r_json.read())

        self.username: str = data["username"] if "username" in data else ""
        self.password: str = data["password"] if "password" in data else ""
        self.steam_login_secure: str = data["steam_login_secure"] if "steam_login_secure" in data else ""
        self.game_whitelist: list[str] = data["game_whitelist"] if "game_whitelist" in data else []

    def update(self: Self, file_name: str = "config") -> None:
        with open(__location__ / f"{file_name}.json", 'w', encoding="utf-8", newline='') as w_json:
            json.dump(self.__dict__, w_json, indent=4, ensure_ascii=False)

async def fetch_table(cfg: Config, url: str) -> str:
    headers = {"Cookie": f"steamLoginSecure={cfg.steam_login_secure}"}
    resp = await decode_http_request(url, headers=headers)

    parsed_html = HTMLTableParser()
    parsed_html.feed(resp)
    try:
        result = parsed_html.tables[0][1:]
    except IndexError:
        cfg.steam_login_secure = await login_request(cfg)
        cfg.update()
        return await fetch_table(cfg, url)

    return result

async def iterate_remote_table(cfg: Config, current_dir: pathlib.Path, remote_table: list[str]) -> None:
    tasks = []
    for game_row in remote_table:
        download_tbl = await fetch_table(cfg, game_row[3])
        game_row[0] = game_row[0].replace(":", "").replace("!", "").replace("?", "")
        game_dir = pathlib.Path(current_dir / game_row[0])
        if not game_dir.exists():
            game_dir.mkdir(parents=True, exist_ok=True)

        for download_row in list(filter(lambda x: len(x[1]) > 0, download_tbl)):
            task = asyncio.create_task(download_game_row(cfg, game_dir, download_row))
            tasks.append(task)
            
        print(f"Downloads started for: {game_row[0]}")
        
    await asyncio.gather(*tasks)

async def download_game_row(cfg: Config, game_dir: str, download_row: list[str]) -> None:
    full_name = (f"%{download_row[0]}%{download_row[1]}" if len(download_row[0]) > 0 else download_row[1])
    full_name = full_name.replace("\\", "%").replace("/", "%").replace(":", "").replace("!", "").replace("?", "")
    headers = {"Cookie": f"steamLoginSecure={cfg.steam_login_secure}"}
    data = await read_http_request(download_row[4], headers=headers)

    file_name = pathlib.Path(game_dir / full_name)
    with open(file_name, 'wb') as w_data:
        w_data.write(data)

async def http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> HTTPResponse:
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    headers.update({"User-Agent": user_agent})
    req = urllib.request.Request(url, headers=headers, data=data)
    return await asyncio.get_event_loop().run_in_executor(None, urllib.request.urlopen, req)

async def read_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> bytes:
    return (await http_request(url, headers=headers, data=data)).read()

async def decode_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> str:
    return (await read_http_request(url, headers=headers, data=data)).decode("utf-8")

async def json_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> dict[str, str]:
    return json.loads(await decode_http_request(url, headers=headers, data=data))

def encrypt_password(password: str, mod: str, exp: str) -> bytes:
    mod: int = int(mod, 16)
    exp: int = int(exp, 16)
    rsa_key: RSA.RsaKey = RSA.construct((mod, exp))
    rsa: PKCS1_v1_5.PKCS115_Cipher = PKCS1_v1_5.new(rsa_key)

    encrypted_password: bytes = rsa.encrypt(password.encode("utf-8"))
    return base64.b64encode(encrypted_password)

async def login_request(cfg: Config) -> str:
    username: str = cfg.username if cfg.username != "" else input("Enter username: ").strip()
    password: str = cfg.password if cfg.password != "" else input("Enter password: ").strip()
    data: bytes = b"username=" + username.encode("utf-8")
    rsa_url: str = "https://steamcommunity.com/login/getrsakey/"
    resp: dict[str, str] = await json_http_request(rsa_url, data=data)

    key_mod: str = resp["publickey_mod"]
    key_exp: str = resp["publickey_exp"]
    timestamp: str = resp["timestamp"]
    encrypted_password: bytes = encrypt_password(password, key_mod, key_exp)

    data += b"&password=" + urllib.parse.quote_plus(encrypted_password).encode("utf-8")
    data += b"&rsatimestamp=" + timestamp.encode("utf-8")

    login_url: str = "https://steamcommunity.com/login/dologin/"
    resp: dict[str, str] = await json_http_request(login_url, data=data)
    if not resp["success"]:
        two_factor_code = input("Enter two factor code: ").strip()
        data2: bytes = b"&twofactorcode=" + two_factor_code.encode("utf-8")
        data2 += b"&remember_login=true"
        resp: dict[str, str] = await json_http_request(login_url, data=data + data2)

    transfer_params: dict[str, str] = resp["transfer_parameters"]
    data2: bytes = b"&steamid=" + transfer_params["steamid"].encode("utf-8")
    data2 += b"&token_secure=" + transfer_params["token_secure"].encode("utf-8")
    data2 += b"&auth=" + transfer_params["auth"].encode("utf-8")

    transfer_url: str = "https://store.steampowered.com/login/transfer"
    resp: HTTPResponse = await http_request(transfer_url, data=data + data2)
    cookie_rgx: re.Pattern = re.compile(r"steamLoginSecure=([\w%]+);", re.IGNORECASE)
    rgx_match: re.Match[str] = cookie_rgx.search(resp.getheader("Set-Cookie"))

    return rgx_match.group(1)

async def main(_: list[str]) -> bool:
    cfg = Config()
    result_dir = pathlib.Path(__location__ / "Results")
    storage_url: str = "https://store.steampowered.com/account/remotestorage"

    if not result_dir.exists():
        result_dir.mkdir(parents=True, exist_ok=True)

    remote_table = list(filter(lambda x: len(x[0]) > 0, await fetch_table(cfg, storage_url)))
    if len(cfg.game_whitelist) > 0:
        remote_table = list(filter(lambda x: x[0] in cfg.game_whitelist, remote_table))

    current_dir = pathlib.Path(result_dir / datetime.date.today().strftime("%y%m%d"))
    if  not current_dir.exists():
        current_dir.mkdir(parents=True, exist_ok=True)

    await iterate_remote_table(cfg, current_dir, remote_table)

    return True

if __name__ == "__main__":
    import sys
    asyncio.run(main(sys.argv[1:]))
