import requests

def member_for_card(card_data):
    card_data = card_data.split(",")
    card_data = [int(c) for c in card_data]
    card_data = ["%02x" % c for c in card_data]
    return get_member("".join(card_data))

def get_member(c_id):
    auth_endpoint = "http://10.25.172.200:5000/auth"
    api_endpoint = "http://10.25.172.200:5000/user?uid=" + c_id
    username = "makerapi"
    password = "***REMOVED***"

    r = requests.post(auth_endpoint, json={
        "username": username,
        "password": password
    })
    r = r.json()
    token = r["access_token"]
    token = "JWT " + token

    r = requests.get(api_endpoint, headers={
        "Authorization": token
    })
    return r.text


print(member_for_card("195,87,179,125"))