#!/usr/bin/env python
# -*- coding: utf8 -*-
#
#    Copyright 2014,2018 Mario Gomez <mario.gomez@teubi.co>
#
#    This file is part of MFRC522-Python
#    MFRC522-Python is a simple Python implementation for
#    the MFRC522 NFC Card Reader for the Raspberry Pi.
#
#    MFRC522-Python is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    MFRC522-Python is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with MFRC522-Python.  If not, see <http://www.gnu.org/licenses/>.
#

import RPi.GPIO as GPIO
from .MFRC522 import MFRC522
import requests
import os


def member_for_card(card_data, token):
    card_data = card_data.split(",")
    card_data = [int(c) for c in card_data]
    card_data = ["%02x" % c for c in card_data]
    return get_member("".join(card_data), token)


def get_member(c_id, maker_api_token):
    api_endpoint = "http://10.25.172.200:5000/user?uid=" + c_id

    maker_api_token = "JWT " + maker_api_token

    r = requests.get(api_endpoint, headers={
        "Authorization": maker_api_token
    })
    return r.json()["MemberID"]


def open_reader():
    auth_endpoint = "http://10.25.172.200:5000/auth"
    username = "makerapi"

    dirname, _ = os.path.split(os.path.abspath(__file__))
    with open(os.path.join(dirname, "pw.txt"), 'r') as f:
        password = f.read()

    r = requests.post(auth_endpoint, json={
        "username": username,
        "password": password
    })
    r = r.json()
    maker_api_token = r["access_token"]
    return MFRC522(), maker_api_token


def read_once(MIFAREReader, token):
    # Welcome message
    # print("Welcome to the MFRC522 data read example")
    # print("Press Ctrl-C to stop.")

    # This loop keeps checking for chips. If one is near it will get the UID and authenticate
    # Scan for cards
    (status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)

    # If a card is found
    if status == MIFAREReader.MI_OK:
        pass
        # print("Card detected")

    # Get the UID of the card
    (status, uid) = MIFAREReader.MFRC522_Anticoll()

    # If we have the UID, continue
    if status == MIFAREReader.MI_OK:

        # Print UID
        # print(("Card read UID: %s,%s,%s,%s" % (uid[0], uid[1], uid[2], uid[3])))
        card = "%s,%s,%s,%s" % (uid[0], uid[1], uid[2], uid[3])

        return member_for_card(card, token)
