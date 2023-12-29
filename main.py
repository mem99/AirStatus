from bleak import BleakScanner
from asyncio import new_event_loop, set_event_loop, get_event_loop
from time import sleep, time_ns
from binascii import hexlify
from json import dumps
from sys import argv
from datetime import datetime

# Configure update duration (update after n seconds)
UPDATE_DURATION = 1
MIN_RSSI = -70
AIRPODS_MANUFACTURER = 76
AIRPODS_DATA_LENGTH = 54
RECENT_BEACONS_MAX_T_NS = 10000000000  # 10 Seconds

recent_beacons = []


def get_best_result(device_and_advertisement):
    recent_beacons.append({
        "time": time_ns(),
        "device": device_and_advertisement
    })
    strongest_beacon = None
    i = 0
    while i < len(recent_beacons):
        if(time_ns() - recent_beacons[i]["time"] > RECENT_BEACONS_MAX_T_NS):
            recent_beacons.pop(i)
            continue
        if (strongest_beacon == None or strongest_beacon[1].rssi < recent_beacons[i]["device"][1].rssi):
            strongest_beacon = recent_beacons[i]["device"]
        i += 1

    if (strongest_beacon != None and strongest_beacon[0].address == device_and_advertisement[0].address):
        strongest_beacon = device_and_advertisement

    return strongest_beacon


# Getting data with hex format
async def get_device():
    # Scanning for devices
    devices = await BleakScanner.discover(return_adv=True)
    for _, d in devices.items():
        # Checking for AirPods
        d = get_best_result(d) # Conflicts with other bluetooth devices
        ad = d[1] #Advertisement
        d = d[0] #Device
        if ad.rssi >= MIN_RSSI and AIRPODS_MANUFACTURER in ad.manufacturer_data.keys():
            data_hex = hexlify(bytearray(ad.manufacturer_data[AIRPODS_MANUFACTURER]))
            if len(data_hex) == AIRPODS_DATA_LENGTH and int(chr(data_hex[1]), 16) == 7:
                return [d.address, data_hex]
    return [0, False]


# Same as get_device() but it's standalone method instead of async
def get_data_hex():
    new_loop = new_event_loop()
    set_event_loop(new_loop)
    loop = get_event_loop()
    a = loop.run_until_complete(get_device())
    loop.close()
    return a


# Getting data from hex string and converting it to dict(json)
# Getting data from hex string and converting it to dict(json)
def get_data():
    device, raw = get_data_hex()

    # Return blank data if airpods not found
    if not raw:
        return dict(status=0, model="AirPods not found")

    flip: bool = is_flipped(raw)

    # On 7th position we can get AirPods model, gen1, gen2, Pro or Max
    if chr(raw[7]) == 'e':
        model = "AirPodsPro"
    elif chr(raw[7]) == '4':
        model = "AirPodsPro2"
    elif chr(raw[7]) == '3':
        model = "AirPods3"
    elif chr(raw[7]) == 'f':
        model = "AirPods2"
    elif chr(raw[7]) == '2':
        model = "AirPods1"
    elif chr(raw[7]) == 'a':
        model = "AirPodsMax"
    else:
        model = "unknown"

    # Checking left AirPod for availability and storing charge in variable
    status_tmp = int("" + chr(raw[12 if flip else 13]), 16)
    left_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # Checking right AirPod for availability and storing charge in variable
    status_tmp = int("" + chr(raw[13 if flip else 12]), 16)
    right_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # Checking AirPods case for availability and storing charge in variable
    status_tmp = int("" + chr(raw[15]), 16)
    case_status = (100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1))

    # On 14th position we can get charge status of AirPods
    charging_status = int("" + chr(raw[14]), 16)
    charging_left:bool = (charging_status & (0b00000010 if flip else 0b00000001)) != 0
    charging_right:bool = (charging_status & (0b00000001 if flip else 0b00000010)) != 0
    charging_case:bool = (charging_status & 0b00000100) != 0

    # Return result info in dict format
    return dict(
        address=device,
        status=1,
        charge=dict(
            left=left_status,
            right=right_status,
            case=case_status
        ),
        charging_left=charging_left,
        charging_right=charging_right,
        charging_case=charging_case,
        model=model,
        date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        raw=raw.decode("utf-8")
    )


# Return if left and right is flipped in the data
def is_flipped(raw):
    return (int("" + chr(raw[10]), 16) & 0x02) == 0


def run():
    output_file = argv[-1]

    while True:
        data = get_data()

        if data["status"] == 1:
            json_data = dumps(data)
            if len(argv) > 1:
                f = open(output_file, "a")
                f.write(json_data+"\n")
                f.close()
            else:
                print(json_data, flush=True)

        sleep(UPDATE_DURATION)


if __name__ == '__main__':
    run()
