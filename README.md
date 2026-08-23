# Lotus Lantern (HA) — ELK-BLEDDM Custom Integration

A purpose-built Home Assistant custom component for `ELK-BLEDDM` BLE LED
strips (and compatible variants: `ELK-BLEDOM`, `ELK-BLEDOB`, `MELK`,
`LEDBLE`), using the exact protocol reverse engineered from the decompiled
Lotus Lantern Android app (`com.easylink.colorful`, package `wl.smartled`).

## Why a Custom Integration Instead of the HACS `elkbledom` Component

- Uses the **exact** byte layout confirmed from this specific app/firmware
  variant, rather than generic community-maintained protocol guesses.
- Adds support for modes the stock `elkbledom` integration doesn't expose:
  effect selection with named effects, effect speed, and a path to add
  music-reactive color and mic sensitivity as separate services later.
- Fully async, uses `bleak-retry-connector` and Home Assistant's Bluetooth
  integration, so it works transparently through an ESPHome Bluetooth
  proxy — no extra proxy configuration needed beyond active-mode discovery.

## File Layout

```
custom_components/
  elk_bleddm/
    __init__.py
    manifest.json
    const.py
    config_flow.py
    light.py
    strings.json
hacs.json
```

## Installing Locally (fastest path)

1. Copy the `custom_components/elk_bleddm/` folder into your HA config
   directory: `config/custom_components/elk_bleddm/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search
   **"ELK-BLEDDM"**. If your strip advertised recently, it should appear as
   a discovered device; otherwise you'll get a manual MAC address field.

## Installing via HACS (as a custom repo)

1. In HACS → Integrations → the "..." menu → **Custom repositories**, add
   `https://github.com/Tech-Morph/Lotus-Lantern-HA`, category "Integration".
2. Install "ELK-BLEDDM Lotus Lantern Light" from HACS, restart HA, then add
   it the same way as above.

## What's Implemented

- Power on/off
- RGB color
- Brightness
- Named effects list (22 built-in modes decoded from the protocol)
- `light.turn_on(effect=...)` support via HA's standard effect parameter

## What's Stubbed But Not Yet Wired to Entities

`const.py` includes builders for music-reactive color, mic on/off, mic
sensitivity, mic EQ mode, color temperature, timers, and pin-sequence remap
— all confirmed working byte layouts from the decompiled app. These aren't
exposed as entities yet; open an issue or PR if you want them added as
`number`/`switch` platforms.

## Protocol Reference

All commands follow `7E [len] [cmd] ... EF` framing, written to
characteristic `0000fff3-0000-1000-8000-00805f9b34fb` on service
`0000fff0-0000-1000-8000-00805f9b34fb`. See `custom_components/elk_bleddm/const.py`
for the full byte-level command table with inline docstrings.

## Troubleshooting

- **Not discovered automatically**: confirm your ESPHome proxy has
  `active: true` under `bluetooth_proxy:` in its YAML — passive mode can't
  support connectable writes.
- **Connection fails / no response**: make sure the strip isn't still
  paired to the Lotus Lantern phone app; BLE devices in this family
  typically only accept one active GATT connection at a time.
- **Colors look swapped**: some ELK variants wire RGB channels in a
  different physical order. Use `cmd_pin_sequence()` from `const.py` to
  remap channel order if red/blue (or similar) appear swapped.
