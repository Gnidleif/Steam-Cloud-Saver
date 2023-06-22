#!/usr/bin/python3
"""
Downloads any relevant files from the Steam Cloud
"""
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
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()

class Config:
    """
    Contains the config data
    """
    def __init__(self: Self, file_name: str = "config"):
        """
        Initializes the config object

        :param file_name: The file name to read from
        """
        with open(SCRIPT_DIR / f"{file_name}.json", 'r', encoding="utf-8", newline='') as r_json:
            data: dict[str, str] = json.loads(r_json.read())

        self.username: str = data["username"] if "username" in data else ""
        self.password: str = data["password"] if "password" in data else ""
        self.steam_login_secure: str = data["steam_login_secure"] if "steam_login_secure" in data else ""
        self.game_whitelist: list[str] = data["game_whitelist"] if "game_whitelist" in data else []

    def update(self: Self, file_name: str = "config") -> None:
        """
        Writes all the config data to the config file

        :param file_name: The file name to write to
        """
        with open(SCRIPT_DIR / f"{file_name}.json", 'w', encoding="utf-8", newline='') as w_json:
            json.dump(self.__dict__, w_json, indent=4, ensure_ascii=False)

async def fetch_table(cfg: Config, url: str) -> str:
    """
    Fetches the HTML table from the passed url

    :param cfg: The config object
    :param url: The url to fetch
    """
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
    """
    Iterates through the remote table and downloads the files

    :param cfg: The config object
    :param current_dir: The current directory
    :param remote_table: The remote table
    """
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
    """
    Downloads the file from the passed download row

    :param cfg: The config object
    :param game_dir: The game directory
    :param download_row: The download row
    """
    full_name = (f"%{download_row[0]}%{download_row[1]}" if len(download_row[0]) > 0 else download_row[1])
    full_name = full_name.replace("\\", "%").replace("/", "%").replace(":", "").replace("!", "").replace("?", "")
    headers = {"Cookie": f"steamLoginSecure={cfg.steam_login_secure}"}
    data = await read_http_request(download_row[4], headers=headers)

    file_name = pathlib.Path(game_dir / full_name)
    with open(file_name, 'wb') as w_data:
        w_data.write(data)

async def http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> HTTPResponse:
    """
    Makes a http request to the passed url

    :param url: The url to request
    :param headers: The headers to send
    :param data: The data to send
    """
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    headers.update({"User-Agent": user_agent})
    req = urllib.request.Request(url, headers=headers, data=data)
    return await asyncio.get_event_loop().run_in_executor(None, urllib.request.urlopen, req)

async def read_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> bytes:
    """
    Returns a byte string from the passed url

    :param url: The url to request
    :param headers: The headers to send
    :param data: The data to send
    """
    return (await http_request(url, headers=headers, data=data)).read()

async def decode_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> str:
    """
    Returns a decoded string from the passed url

    :param url: The url to request
    :param headers: The headers to send
    :param data: The data to send
    """
    return (await read_http_request(url, headers=headers, data=data)).decode("utf-8")

async def json_http_request(url: str, headers: dict[str, str] = {}, data: bytes = None) -> dict[str, str]:
    """
    Returns a json object from the passed url

    :param url: The url to request
    :param headers: The headers to send
    :param data: The data to send
    """
    return json.loads(await decode_http_request(url, headers=headers, data=data))

def encrypt_password(password: str, mod: str, exp: str) -> bytes:
    """
    Encrypts the passed password using RSA

    :param password: The password to encrypt
    :param mod: The RSA modulus
    :param exp: The RSA exponent
    """
    mod: int = int(mod, 16)
    exp: int = int(exp, 16)
    rsa_key: RSA.RsaKey = RSA.construct((mod, exp))
    rsa: PKCS1_v1_5.PKCS115_Cipher = PKCS1_v1_5.new(rsa_key)

    encrypted_password: bytes = rsa.encrypt(password.encode("utf-8"))
    return base64.b64encode(encrypted_password)

async def login_request(cfg: Config) -> str:
    """
    Handle login requests to Steam
    Supports regular login or 2FA

    :param cfg: The config object
    """
    username: str = cfg.username if cfg.username != "" else input("Enter username: ").strip()
    password: str = cfg.password if cfg.password != "" else input("Enter password: ").strip()
    data: bytes = b"username=" + username.encode("utf-8")
    rsa_url: str = "https://steamcommunity.com/login/getrsakey/"
    resp: dict[str, str] = await json_http_request(rsa_url, data=data)

    encrypted_password: bytes = encrypt_password(password, resp["publickey_mod"], resp["publickey_exp"])
    timestamp: str = resp["timestamp"]

    data += b"&password=" + urllib.parse.quote_plus(encrypted_password).encode("utf-8")
    data += b"&rsatimestamp=" + timestamp.encode("utf-8")

    login_url: str = "https://steamcommunity.com/login/dologin/"
    resp: dict[str, str] = await json_http_request(login_url, data=data)
    if not resp["success"]:
        two_factor_code = input("Enter two factor code: ").strip()
        data2: bytes = b"&twofactorcode=" + two_factor_code.encode("utf-8")
        data2 += b"&remember_login=true"
        resp: dict[str, str] = await json_http_request(login_url, data=data + data2)

    data2: bytes = b"&steamid=" + resp["transfer_parameters"]["steamid"].encode("utf-8")
    data2 += b"&token_secure=" + resp["transfer_parameters"]["token_secure"].encode("utf-8")
    data2 += b"&auth=" + resp["transfer_parameters"]["auth"].encode("utf-8")

    transfer_url: str = "https://store.steampowered.com/login/transfer"
    resp: HTTPResponse = await http_request(transfer_url, data=data + data2)
    cookie_rgx: re.Pattern = re.compile(r"steamLoginSecure=([\w%]+);", re.IGNORECASE)
    rgx_match: re.Match[str] = cookie_rgx.search(resp.getheader("Set-Cookie"))

    return rgx_match.group(1)

async def main(_: list[str]) -> bool:
    """
    Main function of the program
    """
    cfg = Config()
    result_dir = pathlib.Path(SCRIPT_DIR / "Results")
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
