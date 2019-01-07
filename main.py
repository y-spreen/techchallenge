from random import randint
from datetime import datetime
from time import sleep
from threading import Thread
UHF_WINDOW = 10  # seconds
CARD_WINDOW = 5  # seconds
DELAY = .1  # 10Hz


def read_uhf_ids():
    return [randint(0, 10)]


def read_card():
    return None if randint(0, 1) else 7


CARD_EVENT = None
ENTER_EVENTS = []
EXIT_EVENTS = []


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
    reading = None

    while True:
        sleep(DELAY)

        card = read_card()
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
    g = '.#'[g]
    y = '.#'[y]
    r = '.#'[r]
    b = '.#'[b]
    print('   '+g+y+r+b+'      ', end="\r")


def light_thread():
    global LIGHT

    is_one_time = [False, False, False, False, True, True]
    # g y r b
    cmds = [
        [(0, 0, 0, 0)] * 28 + [(1, 0, 0, 0)] * 2,
        [(0, 0, 0, 0)] * 10 + [(0, 1, 0, 0)] * 10,
        [(0, 0, 0, 0)] * 5 + [(0, 0, 1, 0)] * 5,
        [(0, 0, 0, 0)] * 2 + [(0, 0, 1, 0)] * 2,
        [(0, 0, 0, 0)] * 4 + [(0, 0, 0, 1)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(0, 0, 0, 1)] * 2,
        [(0, 0, 0, 0)] * 2 + [(1, 0, 0, 0)] * 2 +
        [(0, 1, 0, 0)] * 2 + [(0, 0, 1, 0)] * 2 +
        [(0, 0, 0, 1)] * 2 + [(0, 0, 1, 0)] * 2 +
        [(0, 1, 0, 0)] * 2 + [(1, 0, 0, 0)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(1, 1, 1, 1)] * 2 +
        [(0, 0, 0, 0)] * 2 + [(1, 1, 1, 1)] * 2,
    ]

    tick = 0
    light = LIGHT
    while True:
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
    global CARD_EVENT, EXIT_EVENTS, ENTER_EVENTS, LIGHT
    booked = {}
    in_booking = []
    in_returning = []
    booking_card = None

    while True:
        sleep(DELAY)

        card_event = CARD_EVENT
        CARD_EVENT = None
        exit_events = EXIT_EVENTS
        EXIT_EVENTS = []
        enter_events = ENTER_EVENTS
        ENTER_EVENTS = []

        for e in exit_events:
            print(' x', end="\r")
            if e in in_booking:
                in_booking = filter(lambda b: b != e, in_booking)
            elif e in in_returning:
                in_returning = filter(lambda b: b != e, in_returning)
            else:
                LIGHT = Light.error
        for e in enter_events:
            print(' e', end="\r")
            if booked.get(e, None) is None:
                in_booking.append(e)
                LIGHT = Light.warning
            else:
                in_returning.append(e)
                del booked[e]
                LIGHT = Light.notification
        if card_event is not None:
            print(' c', end="\r")
            if len(in_booking) > 0:
                for b in in_booking:
                    booked[b] = card_event
                LIGHT = Light.notification


def uhf_thread():
    readings = []
    sleep(5)

    while True:
        sleep(DELAY)

        ids = read_uhf_ids()
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


if __name__ == "__main__":
    Thread(target=uhf_thread).start()
    Thread(target=card_thread).start()
    Thread(target=booking_thread).start()
    Thread(target=light_thread).start()
