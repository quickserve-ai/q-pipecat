import pprint

import requests
import os
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv(override=True)
elif os.path.exists("../.env"):
    load_dotenv("../.env")
elif os.path.exists("../../.env"):
    load_dotenv("../../.env")

daily_token = os.getenv("DAILY_API_KEY")


def create_daily_room_with_sip(room_name, token):
    url = f"https://api.daily.co/v1/rooms/{room_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "properties": {
            "sip": {
                "sip_mode": "dial-in",
                "display_name": "SIP Caller"
            }
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()


def configure_pinless_dialin(token, purchased_number, webhook_url):
    url = 'https://api.daily.co/v1/'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        'properties': {
            'pinless_dialin': [
                {
                    'phone_number': purchased_number,
                    'room_creation_api': webhook_url,
                    # 'name_prefix': name_prefix,
                    # 'hmac': hmac_secret
                },
                {
                    'room_creation_api': webhook_url,
                    'name_prefix': 'twilio-interconnect'
                }
            ]
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

pprint.pprint(configure_pinless_dialin(daily_token, "+14155820995", "https://honest-loudly-sloth.ngrok-free.app/daily_start_bot"))
