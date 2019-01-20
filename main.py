from threading import Thread
from time import sleep
from datetime import datetime
from random import randint
import subprocess
import signal
import os
ON_PI = False
if os.uname()[4][:3] == 'arm':
    ON_PI = True
    from uhf import call_read as read_uhf
    from uhf import prepare as prepare_uhf
    from card.mfrc.Read import read_once
    from card.mfrc.Read import open_reader as open_card_reader
    import RPi.GPIO as GPIO
UHF_WINDOW = 10  # seconds
CARD_WINDOW = 5  # seconds
DELAY = .1  # 10Hz
USE_API = False


def read_uhf_ids(node, method_id, val):
    return read_uhf(node, method_id, val)


def read_card(reader, token):
    return read_once(reader, token)


CARD_EVENT = None
ENTER_EVENTS = []
EXIT_EVENTS = []
DO_STOP = False


def card_read(c):
    global CARD_EVENT
    CARD_EVENT = c


def id_exited(i):
    global EXIT_EVENTS
    EXIT_EVENTS.append(i)


def id_entered(i):
    global ENTER_EVENTS
    ENTER_EVENTS.append(i)


def card_thread():
    global DO_STOP, ON_PI, USE_API

    if not ON_PI:
        return

    reading = None
    reader, token = open_card_reader(USE_API)

    while not DO_STOP:
        sleep(DELAY)

        card = read_card(reader, token)
        if card is not None:
            if reading is None or reading[0] != card:
                card_read(card)
            reading = (card, datetime.now())

        elif reading is not None:
            if (datetime.now() - reading[1]).total_seconds() > CARD_WINDOW:
                reading = None


class Light:
    """
    0: blink green (idle)       ____*_
    1: pulse yellow             ___***
    2: flash red                _*_*_*
    3: flash red fast           _*_*_*
    4: blue blinks (one time)   ___*_*
    5: flash all lights (start) _*#+~_
    """
    idle = 0
    warning = 1
    mistake = 2
    error = 3
    notification = 4
    initial = 5


LIGHT = Light.initial


def set_light(g, y, r, b):
    global DO_STOP, ON_PI
    if DO_STOP:
        return
    GPIO.output(7, GPIO.LOW if r else GPIO.HIGH)
    GPIO.output(11, GPIO.LOW if y else GPIO.HIGH)
    GPIO.output(13, GPIO.LOW if g else GPIO.HIGH)
    GPIO.output(15, GPIO.LOW if b else GPIO.HIGH)


def light_thread():
    global LIGHT, DO_STOP

    if not ON_PI:
        return

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(7, GPIO.OUT)
    GPIO.setup(11, GPIO.OUT)
    GPIO.setup(13, GPIO.OUT)
    GPIO.setup(15, GPIO.OUT)

    is_one_time = [False, False, False, False, True, True]
    # g y r b
    cmds = [
        [(0, 0, 0, 0)] * 28 + [(1, 0, 0, 0)] * 2,
        [(0, 0, 0, 0)] * 10 + [(0, 1, 0, 0)] * 10,
        [(0, 0, 0, 0)] * 5 + [(0, 0, 1, 0)] * 5,
        [(0, 0, 0, 0)] * 2 + [(0, 0, 1, 0)] * 2,
        [(0, 0, 0, 0)] * 4 + [(0, 0, 0, 1)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(0, 0, 0, 1)] * 2,
        [(0, 0, 0, 0)] * 2 + [(0, 0, 1, 0)] * 2 +
        [(0, 1, 0, 0)] * 2 + [(1, 0, 0, 0)] * 2 +
        [(0, 0, 0, 1)] * 2 + [(1, 0, 0, 0)] * 2 +
        [(0, 1, 0, 0)] * 2 + [(0, 0, 1, 0)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(1, 1, 1, 1)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(1, 1, 1, 1)] * 2,
    ]

    tick = 0
    light = LIGHT
    while not DO_STOP:
        sleep(DELAY)

        if LIGHT != -1:
            if light != LIGHT:
                tick = 0
            light = LIGHT
            LIGHT = -1

        set_light(*cmds[light][tick])

        tick += 1
        if tick >= len(cmds[light]) and is_one_time[light]:
            tick = light = 0
            LIGHT = -1
        tick %= len(cmds[light])


def booking_thread():
    global CARD_EVENT, EXIT_EVENTS, ENTER_EVENTS, LIGHT, DO_STOP, ON_PI, SOUND
    booked = {}
    in_booking = []
    in_returning = []
    booking_card = None
    error_stage = None

    while not DO_STOP:
        sleep(DELAY)

        card_event = CARD_EVENT
        CARD_EVENT = None
        exit_events = EXIT_EVENTS
        EXIT_EVENTS = []
        enter_events = ENTER_EVENTS
        ENTER_EVENTS = []

        for e in exit_events:
            if ON_PI:
                print('exit ' + str(e))
            if error_stage is not None:
                continue
            if e in in_booking:
                in_booking = [b for b in filter(lambda b: b != e, in_booking)]
                if booked.get(e, None) is None:
                    LIGHT = Light.mistake
                    SOUND = "do_not_leave.mp3"
                    error_stage = (1, e, datetime.now())
                    in_booking = []
                    in_returning = []
            elif e in in_returning:
                in_returning = [b for b in filter(
                    lambda b: b != e, in_returning)]
        for e in enter_events:
            if ON_PI:
                print('enter ' + str(e))
            if error_stage is not None:
                if error_stage[1] != e:
                    continue
                # recover error
                error_stage = None
            if booked.get(e, None) is None:
                in_booking.append(e)
                LIGHT = Light.warning
                SOUND = "please_place.mp3"
            else:
                in_returning.append(e)
                del booked[e]
                LIGHT = Light.notification
                SOUND = "returned.mp3"
        if card_event is not None:
            if ON_PI:
                print('card ' + card_event)
            if error_stage is not None:
                continue
            if len(in_booking) > 0:
                for b in in_booking:
                    booked[b] = card_event
                LIGHT = Light.notification
                SOUND = "checked.mp3"
        if error_stage is not None:
            error_lengths = [0, 3, 6, 9999999]
            stage = error_stage[0]
            if (datetime.now() - error_stage[2]).total_seconds() >= error_lengths[stage]:
                # escalate error further
                stage += 1

                error_stage = (stage,
                               error_stage[1], datetime.now())
                if stage == 2:
                    SOUND = "alarm_soon.mp3"
                if stage == 3:
                    LIGHT = Light.error
                    SOUND = "alarm.mp3"


def uhf_thread():
    global DO_STOP, ON_PI

    if not ON_PI:
        return

    readings = []
    sleep(5)

    client, node, method_id, val = prepare_uhf()

    try:
        while not DO_STOP:
            sleep(DELAY)

            ids = read_uhf_ids(node, method_id, val)
            for v in ids:
                if v not in [id_ for (id_, _) in readings]:
                    id_entered(v)
                readings.append((v, datetime.now()))

            i = 0
            for v in readings:
                if (datetime.now() - v[1]).total_seconds() > UHF_WINDOW:
                    v = v[0]
                    del readings[i]
                    if v not in [id_ for (id_, _) in readings]:
                        id_exited(v)
                else:
                    i += 1
        client.disconnect()
    except:
        client.disconnect()


def end_read(*_):
    global DO_STOP, ON_PI
    DO_STOP = True

    if ON_PI:
        GPIO.cleanup()


SOUND = None


def sound_thread():
    global DO_STOP, ON_PI, SOUND, DELAY

    loop = {"alarm.mp3": 3.05}

    exe = "omxplayer" if ON_PI else "afplay"
    time = sound = p = None

    while not DO_STOP:
        if SOUND is not None:
            sound = SOUND
            SOUND = None
            if p is not None:
                p.terminate()
            p = subprocess.Popen([exe, sound])
            time = datetime.now()

        l = loop.get(sound, 999999)
        if time is not None and l < (datetime.now() - time).total_seconds():
            SOUND = sound
        elif time is not None:
            if l - (datetime.now() - time).total_seconds() <= 1:
                sleep(DELAY / 3)
            else:
                sleep(DELAY)


def prompt():
    global CARD_EVENT, EXIT_EVENTS, ENTER_EVENTS, DO_STOP

    print("""Commands:
 q:      quit,
 e <id>: enter kit,
 x <id>: exit kit,
 c <id>: place card""")

    while not DO_STOP:
        cmd = input('> ')
        c = cmd[0]
        p = cmd[2:]
        if c == 'q':
            return end_read()
        elif c == 'e':
            ENTER_EVENTS.append(p)
        elif c == 'x':
            EXIT_EVENTS.append(p)
        elif c == 'c':
            CARD_EVENT = p


if __name__ == "__main__":
    signal.signal(signal.SIGINT, end_read)
    Thread(target=uhf_thread).start()
    Thread(target=card_thread).start()
    Thread(target=booking_thread).start()
    Thread(target=light_thread).start()
    Thread(target=sound_thread).start()
    if not ON_PI:
        prompt()
