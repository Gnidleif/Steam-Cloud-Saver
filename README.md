# Steam-Cloud-Saver
Fetches any available files from your Steam cloud storage and stores them locally

## Requirements
Python 3.10 with the following libraries installed:
* typing_extensions
* urllib.request
* html.parser

## How to run
1. Create a config.json in the script directory
2. Open https://store.steampowered.com/account/remotestorage
3. Open dev tools and head to the networks tab
4. Refresh the page and open the request going to remotestorage
5. Grab the "Cookie" value in the request header
6. Remove everything in the cookie string but the value of "steamLoginSecure"
7. Add the following contents to your config.json file:
```json
{
    "steamLoginSecure": "SECURE_COOKIE",
    "gameWhiteList": [
      "game1",
      "game2",
      "game3"
    ]
}
```
8. Note that the game names have to match the names of the list on /remotestorage exactly
9. Run the script
10. The backed up files should be stored in the script directory like this: scriptdir\YYMMDD\Game_Name\file_name

Note: The "gameWhiteList" parameter is optional, if it's not provided the script will simply backup every available game in the list