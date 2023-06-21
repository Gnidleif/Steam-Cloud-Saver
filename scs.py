#!/usr/bin/python3
import pathlib, json, os, threading, urllib.request, re
from typing_extensions import Self
from html_table_parser import HTMLTableParser
from datetime import date
__location__ = pathlib.Path(__file__).parent.resolve()
__results__ = __location__ / "Results"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

class Config:
    def __init__(self: Self, file_name: str = "config"):
        with open(__location__ / f"{file_name}.json", 'r', encoding="utf-8", newline='') as r_json:
            data = json.loads(r_json.read())
        self.game_whitelist = data["game_whitelist"] if "game_whitelist" in data else []
        self.steam_login_secure = data["steam_login_secure"] if "steam_login_secure" in data else ""
        self.username = data["username"]
        self.password = data["password"]

    def update(self: Self, file_name: str = "config") -> None:
        with open(__location__ / f"{file_name}.json", 'w', encoding="utf-8", newline='') as w_json:
            json.dump(self.__dict__, w_json, indent=4, ensure_ascii=False)

def fetch_table(cfg: Config, url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cookie": f"steamLoginSecure={cfg.steam_login_secure}"})
    resp = urllib.request.urlopen(req)

    resp = resp.read().decode("utf-8")
    parsed_html = HTMLTableParser()
    parsed_html.feed(resp)
    try:
        result = parsed_html.tables[0][1:]
    except IndexError:
        cfg.steam_login_secure = login_request(cfg)
        cfg.update()
        return fetch_table(cfg, url)
    
    return result

def iterate_remote_table(cfg: Config, remote_table: list[str]) -> None:
    current_dir = __results__ / date.today().strftime("%y%m%d")
    if not os.path.exists(current_dir):
        current_dir.mkdir(parents=True, exist_ok=True)

    for game_row in remote_table:
        download_tbl = fetch_table(cfg, game_row[3])
        game_dir = current_dir / game_row[0].replace(":", "").replace("!", "").replace("?", "")
        if not os.path.exists(game_dir):
            game_dir.mkdir(parents=True, exist_ok=True)

        start_downloads(cfg, game_dir, download_tbl)
        print(f"Download started for: {game_row[0]}")

def download_game_row(cfg: Config, game_dir: str, download_row: list[str]) -> None:
    full_name = (f"%{download_row[0]}%{download_row[1]}" if len(download_row[0]) > 0 else download_row[1]).replace("/", "%").replace("\\", "%")
    req = urllib.request.Request(download_row[4], headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    with open(game_dir / full_name, 'wb') as w_data:
        w_data.write(data)

def start_downloads(cfg: Config, game_dir: str, game_table: list[str]) -> None:
    threads = []
    for download_row in list(filter(lambda x: len(x[1]) > 0, game_table)):
        threads.append(threading.Thread(target=download_game_row, args=(cfg, game_dir, download_row,)))
        threads[-1].start()

def http_request(url: str, data: bytes) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    f = urllib.request.urlopen(req)
    resp = f.read().decode("utf-8")

    return resp

def encrypt_password(password: str, mod: str, exp: str) -> str:
    import base64
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    mod = int(mod, 16)
    exp = int(exp, 16)
    rsa_key = RSA.construct((mod, exp))
    rsa = PKCS1_v1_5.new(rsa_key)

    encrypted_password = rsa.encrypt(password.encode("utf-8"))
    return base64.b64encode(encrypted_password)

def login_request(cfg: Config) -> None:
    rsa_url = "https://steamcommunity.com/login/getrsakey/"
    resp = json.loads(http_request(rsa_url, b"username=" + cfg.username.encode("utf-8")))
    key_mod = resp["publickey_mod"]
    key_exp = resp["publickey_exp"]
    timestamp = resp["timestamp"]
    encrypted_password = encrypt_password(cfg.password, key_mod, key_exp)

    data = b"username=" + cfg.username.encode("utf-8")
    data += b"&password=" + urllib.parse.quote_plus(encrypted_password).encode("utf-8")
    data += b"&rsatimestamp=" + timestamp.encode("utf-8")

    login_url = "https://steamcommunity.com/login/dologin/"
    resp = json.loads(http_request(login_url, data))
    if resp["success"] == False:
        two_factor_code = urllib.parse.quote_plus(input("Enter two factor code: "))
        data2 = b"&twofactorcode=" + two_factor_code.encode("utf-8")
        data2 += b"&remember_login=true"
        resp = json.loads(http_request(login_url, data + data2))

    transfer_url = "https://store.steampowered.com/login/transfer"
    data2 = b"&steamid=" + resp["transfer_parameters"]["steamid"].encode("utf-8")
    data2 += b"&token_secure=" + resp["transfer_parameters"]["token_secure"].encode("utf-8")
    data2 += b"&auth=" + resp["transfer_parameters"]["auth"].encode("utf-8")
    req = urllib.request.Request(transfer_url, data=data + data2, headers={"User-Agent": UA})
    resp = urllib.request.urlopen(req)

    cookie_rgx = re.compile(r"steamLoginSecure=([\w%]+);", re.IGNORECASE)
    m = cookie_rgx.search(resp.getheader("Set-Cookie"))

    return m.group(1)

def main(args: list[str]) -> bool:
    cfg = Config()
    if not os.path.exists(__results__):
        __results__.mkdir(parents=True, exist_ok=True)

    remote_table = fetch_table(cfg, "https://store.steampowered.com/account/remotestorage")
    if len(cfg.game_whitelist) > 0:
        remote_table = list(filter(lambda x: x[0] in cfg.game_whitelist, remote_table))

    iterate_remote_table(cfg, remote_table)

    return True

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])