import json
import tls_client
import requests
import webbrowser
import keyboard
import time
import base64
import uuid
import os
import re
import ctypes
import threading
from sys import exit
from colorama import Fore, init
from urllib.parse         import urlparse, parse_qs
BASE_URL = 'https://api.vaultcord.com'

colors = {
    "main_colour": Fore.MAGENTA,
    "light_red": Fore.LIGHTRED_EX,
    "yellow": Fore.YELLOW,
    "light_blue": Fore.LIGHTBLUE_EX,
    "green": Fore.LIGHTGREEN_EX,
    "white": Fore.WHITE,
}

def generate_discord_headers(token: str):
    # get Discord build number
    login_html = requests.get("https://discord.com/login").text
    build_match = None
    if '"BUILD_NUMBER":"' in login_html:
        match = re.search(r'"BUILD_NUMBER":"(\d+)"', login_html)
        if match:
            build_match = match.group(1)
    build_number = build_match or "454358"
    # get latest Chrome stable version
    version_data = requests.get(
        "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json").json()
    latest_version = version_data["channels"]["Stable"]["version"]
    milestone = latest_version.split(".")[0]

    # generate UA and client props
    user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{latest_version} Safari/537.36"
    sec_ch_ua = f'"Google Chrome";v="{milestone}", "Not-A.Brand";v="8", "Chromium";v="{milestone}"'

    props = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "pl-PL",
        "has_client_mods": False,
        "browser_user_agent": user_agent,
        "browser_version": latest_version,
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": int(build_number),
        "client_event_source": None,
        "client_launch_id": str(uuid.uuid4()),
        "launch_signature": str(uuid.uuid4()),
        "client_app_state": "focused",
        "client_heartbeat_session_id": str(uuid.uuid4())
    }

    x_super_properties = base64.b64encode(json.dumps(props).encode()).decode()

    headers = {
        "accept": "*/*",
        "accept-language": "en,en-US;q=0.9,en;q=0.8,fr-FR;q=0.7,fr;q=0.6",
        "authorization": token,
        "content-type": "application/json",
        "origin": "https://discord.com",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": user_agent,
        "x-debug-options": "bugReporterEnabled",
        "x-discord-locale": "en-US",
        "x-discord-timezone": "Europe/Warsaw",
        "x-super-properties": x_super_properties
    }

    return headers


def joiner(token, botid, client_secret, redirect_uri, server_id, api_key):
    # Ensure tokens read from file appear to be real, to reduce Discord API spam
    token_parts = token.split('.')
    if len(token_parts) != 3:
        print(
            f"{colors['white']}[-]: {colors['light_red']} The value \"{token}\" isn't a Discord token. Fix your tokens.txt file")
    else:
        # Extract the user ID from the first section of the Discord token
        user_id_base64 = token_parts[0]
        padding = '=' * (4 - len(user_id_base64) % 4)
        user_id_base64 += padding
        user_id_bytes = base64.b64decode(user_id_base64)
        user_id = user_id_bytes.decode('utf-8')

        # Discord fingerprinting security
        session = tls_client.Session(client_identifier=f"chrome_124", random_tls_extension_order=True)

        # Generate dynamic headers for this token
        headers = generate_discord_headers(token)
        headers_cookies = {"user-agent": headers["user-agent"]}
        cookies = dict(session.get(f"https://discord.com/api/v9/experiments", headers=headers_cookies).cookies);
        cookies[
            "__cf_bm"] = "0duPxpWahXQbsel5Mm.XDFj_eHeCKkMo.T6tkBzbIFU-1679837601-0-AbkAwOxGrGl9ZGuOeBGIq4Z+ss0Ob5thYOQuCcKzKPD2xvy4lrAxEuRAF1Kopx5muqAEh2kLBLuED6s8P0iUxfPo+IeQId4AS3ZX76SNC5F59QowBDtRNPCHYLR6+2bBFA==";
        cookies["locale"] = "vi"
        try:
            headers["cookie"] = "; ".join(
                f"{k}={cookies[k]}"
                for k in ["__dcfduid", "__sdcfduid", "__cf_bm", "locale"]
                if k in cookies and cookies[k]
            )

            querystring = {
                "client_id": str(botid),
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": "identify guilds.join",
                "state": str(botid)
            }

            request = session.post(
                f"https://discord.com/api/v9/oauth2/authorize",
                headers=headers,
                cookies=cookies,
                params=querystring,
                json={"permissions": "0", "authorize": True}
            )
            if "location" in request.text:
                answer = request.json()["location"]
                url = urlparse(answer)

                code = parse_qs(url.query).get('code', [None])[0]

                # Exchange code for access token
                post_data = {
                    'client_id': botid,
                    'client_secret': client_secret,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': redirect_uri,
                }
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }

                response = session.post(
                    f'https://discord.com/api/oauth2/token',
                    headers=headers,
                    data=post_data
                )
                if response.status_code == 200:
                    try:
                        json = response.json()

                        access_token = json.get("access_token")
                        refresh_token = json.get("refresh_token")
                        username = f'token_{int(time.time())}'
                    except Exception as e:
                        print(f"{colors['white']}[-]: {colors['light_red']} Caught error while authorizing {e}")
                        return

                    headers = {
                        'Authorization': f'Bearer {api_key}'
                    }

                    json_data = {
                        'serverId': server_id,
                        'userId': user_id,
                        'username': username,
                        'accessToken': access_token,
                        'refreshToken': refresh_token,
                    }

                    # Import member into VaultCord
                    request = requests.post(
                        f'{BASE_URL}/members/import',
                        headers=headers,
                        json=json_data
                    )

                    try:
                        json = request.json()
                        if json.get("success") == True:
                            print(f"{colors['white']}[+]: {colors['green']} Successfully imported token: {token}")
                        else:
                            print(f"{colors['white']}[-]: {colors['light_red']} Failed to import token {request.text}")
                    except Exception as e:
                        print(f"{colors['white']}[-]: {colors['light_red']} Caught error while authorizing {e}")

                else:
                    print(f"{colors['white']}[-]: {colors['light_red']} Failed to exchange code {response.text}")
            else:
                print(f"{colors['white']}[-]: {colors['light_red']} Failed to authorize token {request.text}\n")
        except Exception as e:
            print(f"{colors['white']}[-]: {colors['light_red']} Caught error while authorizing {e}")

def runthread(func, *args_list):
    tokens = open("tokens.txt", "r").read().splitlines()
    threads = []

    for token in tokens:
        thread = threading.Thread(target=func, args=(token, *args_list))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

# Function to check if the file exists and contains the token
def read_token_from_file(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            token = file.read().strip()
        return token
    return None
    
def save_token_to_file(filename, token):
    with open(filename, 'w') as file:
        file.write(token)
    
# Function to validate the token using a GET request
def is_valid_token(token):
    url = f'{BASE_URL}/accounts/settings'
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False
    
# Fetch list of servers
def fetch_servers(api_key):
    url = f'{BASE_URL}/servers'
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        servers = response.json().get('data', [])
        for idx, server in enumerate(servers):
            print(f"{colors['yellow']}{idx + 1}. {colors['white']}{server['name']} {colors['main_colour']}(ID: {server['id']})")
        return servers
    else:
        print(f"Error fetching servers: {response.status_code}")
        return []

# Fetch server settings
def fetch_server_settings(server_id, api_key):
    url = f'{BASE_URL}/servers/{server_id}'
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        server_settings = response.json()
        return server_settings
    else:
        print(f"Error fetching server settings: {response.status_code}")
        return None

# Fetch bot settings
def fetch_bot_settings(bot_id, api_key):
    url = f'{BASE_URL}/bots/{bot_id}'
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        bot_settings = response.json()
        return bot_settings
    else:
        print(f"Error fetching bot settings: {response.status_code}")
        return None

def cleanup():
        print(f"Closing in 3 seconds..")
        time.sleep(3)
        exit()        
        
def main():
    # Check Discord tokens file exists
    if not os.path.exists('tokens.txt'):
        print(f"You must create a {colors['yellow']}tokens.txt{colors['white']} file with your Discord tokens!")
        print(f'Please watch our YouTube tutorial video: {colors["light_blue"]}https://www.youtube.com/watch?v=th1QQlxiyTs')
        cleanup()
        return
        
    print(f'----------------------------------------------------------')
    print(f'{colors["green"]}Welcome!{colors["white"]} Use this to join Discord tokens to your server.')
    print(f'Please watch our YouTube tutorial video: {colors["light_blue"]}https://www.youtube.com/watch?v=th1QQlxiyTs')
    print(f'----------------------------------------------------------\n')
        
    api_key = read_token_from_file('vaultcord_api.txt')
    
    while not api_key or not is_valid_token(api_key):
        if api_key:
            print(f"{colors['light_red']}Invalid token{colors['white']}, please enter a valid Vaultcord API token.")
        else:
            webbrowser.open('https://dash.vaultcord.com/developers')
        api_key = input("Please enter a valid Vaultcord API token: ").strip()
    save_token_to_file('vaultcord_api.txt', api_key)
    
    # Step 1: Fetch and list servers
    servers = fetch_servers(api_key)
    
    if not servers:
        print("No servers on VaultCord account! Create 1 and try again.")
        webbrowser.open('https://dash.vaultcord.com/servers/add')
        cleanup()
        return
        
    server_choice = None

    while server_choice is None or (server_choice < 0 or server_choice >= len(servers)):
        if server_choice is not None:
            print(f'You must select a {colors["yellow"]}NUMBER{colors["white"]} between (1-{len(servers)})')
            print(f'Please watch our YouTube tutorial video: {colors["light_blue"]}https://www.youtube.com/watch?v=th1QQlxiyTs')
    
        # Input validation for numeric input
        try:
            server_choice = int(input(f"Select a server number (1-{len(servers)}): ")) - 1
        except ValueError:
            print(f'{colors["light_red"]}Invalid input!{colors["white"]} Please enter a valid number.')
            server_choice = None  # Reset the choice to keep the loop running
            
    selected_server = servers[server_choice]
    server_id = selected_server['id']
    
    print('Retrieving server..')

    # Step 3: Fetch server settings
    server_settings = fetch_server_settings(server_id, api_key)
    
    if int(server_settings["data"]["botId"]) == 7777:
        print(f'{colors["light_red"]}Our pre-made verified bot can\'t be used for ToS reasons and because we can\'t securely download a public bot token used by 4k+ servers to your computer. Please create a new server with a custom VaultCord bot https://dash.vaultcord.com/bots/add')
        cleanup()
        return

    if server_settings:
        # Step 4: Fetch bot settings
        bot_id = server_settings['data']['botId']
        print('Retrieving bot..')
        bot_settings = fetch_bot_settings(bot_id, api_key)
        if not bot_settings:
            print("No bot linked to VaultCord server! Choose a different VaultCord server.")
            webbrowser.open('https://dash.vaultcord.com/bots/add')
            cleanup()
            return
    else:
        print("Server not found on VaultCord! Choose a different VaultCord server.")
        webbrowser.open('https://dash.vaultcord.com/servers/add')
        cleanup()
        return
        
    bot_token = bot_settings['data']['token']
    bot_clientid = bot_settings['data']['clientId']
    bot_secret = bot_settings['data']['clientSecret']
    
    headers = {
            'authorization': f'Bot {bot_token}'
    }
    # Check Discord bot is valid
    response = requests.get(
        f"https://discord.com/api/applications/@me",
        headers=headers
    )
    if response.status_code != 200:
        print(f'Discord bot invalid. Error: {response.status_code} Check the VaultCord dashboard and update your bot token.')
        webbrowser.open(f'https://dash.vaultcord.com/bots/{bot_id}')
        cleanup()
        return
        
    # Make sure the Discord bot has redirect URL set, needed to authorize members
    json = response.json()
    if len(json.get("redirect_uris")) < 1:
        print('You need to add redirect URL to Discord bot: https://vaultcord.win/auth')
        webbrowser.open(f'https://discord.com/developers/applications/{bot_clientid}/oauth2')
        cleanup()
        return
        
    print(f'{colors["yellow"]}----------------------------------------------------------')
    print('Joining tokens now..')

    runthread(joiner, bot_clientid, bot_secret, json.get("redirect_uris")[0], server_id, api_key)
    # def joiner(token, botid, client_secret, redirect_uri):
    
    print(f"{colors['yellow']}Finished! {colors['white']}Press any key to close...")
    keyboard.read_event()
if __name__ == "__main__":
    try: ctypes.windll.kernel32.SetConsoleTitleW(f"VaultCord token joiner - Watch tutorial video if you need help!")
    except: pass
    init(autoreset=True)
    main()
