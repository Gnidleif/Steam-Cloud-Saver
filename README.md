# Steam-Cloud-Saver
Fetches any available files from your Steam cloud storage and stores them locally

## Requirements
Python 3.10 with the following libraries installed:
* typing_extensions
* urllib.request
* html.parser
* pycryptodome

## How to run
1. Create a config.json file in the script directory
2. Add the following contents to your config.json file, add your real Steam username and password:
```json
{
  "username": "your_username",
  "password": "your_password",
  "gameWhiteList": [
    "game1",
    "game2",
    "game3"
  ]
}
```
3. Note that the game names have to match the names of the list on [remote storage](https://store.steampowered.com/account/remotestorage) exactly
4. Run the script
5. The backed up files should be stored in the script directory like this: scriptdir\YYMMDD\Game_Name\file_name

## Notes
1. Only supports two factor authentication as an added security measure
2. "game_whitelist" in the config.json file is optional, if it's not provided the script will simply backup every available game in the list
3. "username" and "password" in the config.json file are both optional and will have to be provided in the command line when authentication is required if not added to config.json
3. After running once the script will add a "steam_login_secure" parameter which is saved for use by future requests in order to skip logging on every time