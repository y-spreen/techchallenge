import base64
import json
with open("mp3.json", "r") as f:
    parsed_json = json.load(f)

with open("sound.mp3", "wb") as f:
    f.write(base64.b64decode(parsed_json["audioContent"]))
