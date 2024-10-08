""" This file contains the dpCodes for the devices. """

DP_CODES = {
    "103": {"dpCode": "flip", "standardType": "Boolean"},
    "104": {"dpCode": "osd", "standardType": "Boolean"},
    "105": {"dpCode": "private", "standardType": "Boolean"},
    "106": {
        "dpCode": "motion_sensitivity",
        "standardType": "Enum",
        "valueRange": ["0", "1", "2"],
    },
    "108": {
        "dpCode": "nightvision",
        "standardType": "Enum",
        "valueRange": ["0", "1", "2"],
    },
    "134": {"dpCode": "motion_switch", "standardType": "Boolean"},
    "188": {
        "dpCode": "anti_flicker",
        "standardType": "Enum",
        "valueRange": ["0", "1", "2"],
    },
    "201": {
        "dpCode": "feed_num",
        "standardType": "Integer",
        "properties": {"max": 20, "min": 0, "scale": 0, "step": 1},
    },
    "202": {
        "dpCode": "food_weight",
        "standardType": "Integer",
        "properties": {"max": 100, "min": 1, "scale": 1, "step": 1},
    },
    "206": {
        "dpCode": "history_data",
        "standardType": "Integer",
        "properties": {"max": 2147483645, "min": 0, "scale": 1, "step": 1},
    },
    "207": {"dpCode": "schedule", "standardType": "String"},
    "231": {
        "dpCode": "device_volume",
        "standardType": "Integer",
        "properties": {"unit": "", "min": 1, "max": 100, "scale": 1, "step": 1},
    },
    "241": {
        "dpCode": "ipc_player_flip",
        "standardType": "Enum",
        "valueRange": ["flip_rotate_90"],
    },
    "255": {
        "dpCode": "feed_abnormal",
        "standardType": "Integer",
        "properties": {"max": 255, "min": 0, "scale": 0, "step": 1},
    },
}
