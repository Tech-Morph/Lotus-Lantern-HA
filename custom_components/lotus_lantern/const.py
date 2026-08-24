"""Constants and packet builders for the ELK-BLEDDM / Lotus Lantern protocol.

Protocol reverse engineered from the decompiled Lotus Lantern app
(com.easylink.colorful, package wl.smartled) — see
service/BluetoothLEService.java for the original Java source of these
byte layouts.
"""

from __future__ import annotations

DOMAIN = "lotus_lantern"

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

HEADER = 0x7E
FOOTER = 0xEF

# Effect / mode IDs are ORed with 0x80 by the app before sending.
MODE_FLAG = 0x80

EFFECT_NAMES = {
    0: "Jump Red/Green/Blue",
    1: "Jump Red/Green/Blue/Yellow/Cyan/Magenta/White",
    2: "Crossfade Red/Green/Blue",
    3: "Crossfade Seven Color",
    4: "Crossfade Red",
    5: "Crossfade Green",
    6: "Crossfade Blue",
    7: "Crossfade Yellow",
    8: "Crossfade Cyan",
    9: "Crossfade Magenta",
    10: "Crossfade White",
    11: "Crossfade Red/Green",
    12: "Crossfade Red/Blue",
    13: "Crossfade Green/Blue",
    14: "Strobe Red",
    15: "Strobe Green",
    16: "Strobe Blue",
    17: "Strobe Yellow",
    18: "Strobe Cyan",
    19: "Strobe Magenta",
    20: "Strobe White",
    21: "Strobe Seven Color",
}


def _clamp(value: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, int(value)))


def cmd_power(on: bool) -> bytearray:
    """7E 04 04 [01/00] 00 [01/00] FF 00 EF"""
    state = 0x01 if on else 0x00
    return bytearray([HEADER, 0x04, 0x04, state, 0x00, state, 0xFF, 0x00, FOOTER])


def cmd_color(r: int, g: int, b: int) -> bytearray:
    """7E 07 05 03 RR GG BB 10 EF"""
    return bytearray(
        [HEADER, 0x07, 0x05, 0x03, _clamp(r), _clamp(g), _clamp(b), 0x10, FOOTER]
    )


def cmd_music_color(r: int, g: int, b: int) -> bytearray:
    """7E 07 05 03 RR GG BB 20 EF (music-reactive color variant)"""
    return bytearray(
        [HEADER, 0x07, 0x05, 0x03, _clamp(r), _clamp(g), _clamp(b), 0x20, FOOTER]
    )


def cmd_brightness(brightness: int, mode: int = 0xFF) -> bytearray:
    """7E 04 01 BB MM FF FF 00 EF"""
    return bytearray(
        [HEADER, 0x04, 0x01, _clamp(brightness), mode & 0xFF, 0xFF, 0xFF, 0x00, FOOTER]
    )


def cmd_color_temperature(warm: int, cold: int) -> bytearray:
    """7E 06 05 02 WW CC FF 08 EF"""
    return bytearray(
        [HEADER, 0x06, 0x05, 0x02, _clamp(warm), _clamp(cold), 0xFF, 0x08, FOOTER]
    )


def cmd_effect(mode: int) -> bytearray:
    """7E 05 03 [mode|80] 03 FF FF 00 EF"""
    flagged = (mode & 0x7F) | MODE_FLAG
    return bytearray([HEADER, 0x05, 0x03, flagged, 0x03, 0xFF, 0xFF, 0x00, FOOTER])


def cmd_effect_speed(speed: int) -> bytearray:
    """7E 04 02 SS FF FF FF 00 EF"""
    return bytearray(
        [HEADER, 0x04, 0x02, _clamp(speed), 0xFF, 0xFF, 0xFF, 0x00, FOOTER]
    )


def cmd_single_color_preset(index: int) -> bytearray:
    """7E 05 05 01 CC FF FF 08 EF"""
    return bytearray(
        [HEADER, 0x05, 0x05, 0x01, _clamp(index), 0xFF, 0xFF, 0x08, FOOTER]
    )


def cmd_mic_on_off(on: bool) -> bytearray:
    """7E 04 07 [01/00] FF FF FF 00 EF"""
    state = 0x01 if on else 0x00
    return bytearray([HEADER, 0x04, 0x07, state, 0xFF, 0xFF, 0xFF, 0x00, FOOTER])


def cmd_mic_sensitivity(sensitivity: int) -> bytearray:
    """7E 04 06 SS FF FF FF 00 EF"""
    return bytearray(
        [HEADER, 0x04, 0x06, _clamp(sensitivity), 0xFF, 0xFF, 0xFF, 0x00, FOOTER]
    )


def cmd_mic_eq_mode(mode: int) -> bytearray:
    """7E 05 03 [mode|80] 04 FF FF 00 EF"""
    flagged = (mode & 0x7F) | MODE_FLAG
    return bytearray([HEADER, 0x05, 0x03, flagged, 0x04, 0xFF, 0xFF, 0x00, FOOTER])


def cmd_pin_sequence(r: int, g: int, b: int) -> bytearray:
    """7E 06 81 RR GG BB FF 00 EF"""
    return bytearray(
        [HEADER, 0x06, 0x81, _clamp(r), _clamp(g), _clamp(b), 0xFF, 0x00, FOOTER]
    )
