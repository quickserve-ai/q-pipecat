import pprint
import os
import requests

from daily import *
from dotenv import load_dotenv


if os.path.exists(".env"):
    load_dotenv(override=True)
elif os.path.exists("../.env"):
    load_dotenv("../.env")
elif os.path.exists("../../.env"):
    load_dotenv("../../.env")

daily_token = os.getenv("DAILY_API_KEY")

def list_available_numbers(token, areacode='415'):
    url = 'https://api.daily.co/v1/list-available-numbers'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    params = {
        'areacode': areacode
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()


def get_purchased_phone_numbers(token):
    url = 'https://api.daily.co/v1/purchased-phone-numbers'
    headers = {
        'Authorization': f'Bearer {token}'
    }

    response = requests.get(url, headers=headers)
    return response.json()


def buy_phone_number(token, number):
    url = 'https://api.daily.co/v1/buy-phone-number'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        'number': number
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

pprint.pprint(get_purchased_phone_numbers(daily_token))