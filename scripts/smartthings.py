#!/usr/bin/env python3
"""SmartThings thermostat client used by the Ecobee automation workflows."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.smartthings.com/v1"
REQUIRED_THERMOSTAT_CAPABILITIES = {
    "thermostatMode",
    "thermostatCoolingSetpoint",
    "thermostatHeatingSetpoint",
}


def api(method, path, token, payload=None):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SmartThings API HTTP {exc.code}: {body}") from exc


def thermostat_capabilities(device):
    return {
        capability.get("id")
        for component in device.get("components", [])
        for capability in component.get("capabilities", [])
    }


def thermostats(token):
    devices = api("GET", "/devices", token).get("items", [])
    return [
        device
        for device in devices
        if REQUIRED_THERMOSTAT_CAPABILITIES.issubset(
            thermostat_capabilities(device)
        )
    ]


def find_thermostat(token, requested_name):
    requested = requested_name.strip().casefold()
    matches = []

    for device in thermostats(token):
        label = str(device.get("label") or "").strip()
        if label.casefold() == requested:
            matches.append(device)

    if len(matches) != 1:
        available = [
            device.get("label") or device.get("deviceId")
            for device in thermostats(token)
        ]
        raise RuntimeError(
            f"Expected exactly one thermostat labeled {requested_name!r}; "
            f"found {len(matches)}. Available: {available}"
        )

    return matches[0]


def device_status(token, device_id):
    return api("GET", f"/devices/{device_id}/status", token)


def attribute(main, capability, name):
    value = main.get(capability, {}).get(name, {})
    return {
        "value": value.get("value"),
        "unit": value.get("unit"),
    }


def status_summary(raw_status):
    main = raw_status.get("components", {}).get("main", {})
    return {
        "temperature": attribute(
            main, "temperatureMeasurement", "temperature"
        ),
        "humidity": attribute(
            main, "relativeHumidityMeasurement", "humidity"
        ),
        "mode": attribute(
            main, "thermostatMode", "thermostatMode"
        ),
        "supported_modes": attribute(
            main, "thermostatMode", "supportedThermostatModes"
        ),
        "operating_state": attribute(
            main, "thermostatOperatingState", "thermostatOperatingState"
        ),
        "cooling_setpoint": attribute(
            main, "thermostatCoolingSetpoint", "coolingSetpoint"
        ),
        "heating_setpoint": attribute(
            main, "thermostatHeatingSetpoint", "heatingSetpoint"
        ),
    }


def masked_device_id(device_id):
    if len(device_id) <= 8:
        return device_id
    return f"{device_id[:8]}..."


def ensure_fahrenheit(summary, mode):
    key = "cooling_setpoint" if mode == "cool" else "heating_setpoint"
    unit = str(summary.get(key, {}).get("unit") or "").strip().lower()
    if unit not in {"f", "°f", "fahrenheit"}:
        raise RuntimeError(
            f"Expected {key} to report Fahrenheit before sending a command; "
            f"SmartThings returned unit {unit or 'unknown'!r}. Refusing to guess."
        )


def ensure_supported_mode(summary, mode):
    supported = summary.get("supported_modes", {}).get("value")
    if supported and mode not in supported:
        raise RuntimeError(
            f"Thermostat does not report {mode!r} as supported. "
            f"Supported modes: {supported}"
        )


def send_commands(token, device_id, commands):
    response = api(
        "POST",
        f"/devices/{device_id}/commands",
        token,
        {"commands": commands},
    )
    results = response.get("results", [])
    if len(results) != len(commands):
        raise RuntimeError(
            f"SmartThings returned an unexpected command response: {response}"
        )
    bad = [result for result in results if result.get("status") != "ACCEPTED"]
    if bad:
        raise RuntimeError(f"SmartThings did not accept all commands: {response}")
    return response


def matches_requested(summary, mode, temperature):
    actual_mode = summary.get("mode", {}).get("value")
    key = "cooling_setpoint" if mode == "cool" else "heating_setpoint"
    actual_temp = summary.get(key, {}).get("value")

    try:
        temp_matches = abs(float(actual_temp) - float(temperature)) <= 0.6
    except (TypeError, ValueError):
        temp_matches = False

    return actual_mode == mode and temp_matches


def set_thermostat(token, name, mode, temperature, dry_run):
    if mode not in {"heat", "cool"}:
        raise RuntimeError("Mode must be heat or cool.")
    if not 60 <= temperature <= 80:
        raise RuntimeError("Temperature safety limit is 60-80 F.")

    device = find_thermostat(token, name)
    device_id = device["deviceId"]
    label = device.get("label") or device_id

    before = status_summary(device_status(token, device_id))
    print(f"Matched thermostat: {label}")
    print(f"Device ID: {masked_device_id(device_id)}")
    print("Current state:")
    print(json.dumps(before, indent=2))
    print("Requested state:")
    print(
        json.dumps(
            {
                "mode": mode,
                "temperature_f": temperature,
                "dry_run": dry_run,
            },
            indent=2,
        )
    )

    if dry_run:
        print("DRY RUN: no SmartThings commands sent.")
        return

    ensure_fahrenheit(before, mode)
    ensure_supported_mode(before, mode)

    setpoint_capability = (
        "thermostatCoolingSetpoint"
        if mode == "cool"
        else "thermostatHeatingSetpoint"
    )
    setpoint_command = (
        "setCoolingSetpoint"
        if mode == "cool"
        else "setHeatingSetpoint"
    )

    commands = [
        {
            "component": "main",
            "capability": "thermostatMode",
            "command": "setThermostatMode",
            "arguments": [mode],
        },
        {
            "component": "main",
            "capability": setpoint_capability,
            "command": setpoint_command,
            "arguments": [temperature],
        },
    ]

    response = send_commands(token, device_id, commands)
    print("SmartThings command response:")
    print(json.dumps(response, indent=2))

    # SmartThings ACCEPTED means queued, not necessarily applied. Poll briefly
    # so a manual test fails loudly if the thermostat never reflects the request.
    latest = before
    for attempt in range(1, 16):
        time.sleep(2)
        latest = status_summary(device_status(token, device_id))
        if matches_requested(latest, mode, temperature):
            print(f"Verified requested state after {attempt * 2} seconds:")
            print(json.dumps(latest, indent=2))
            return

    print("Last observed state:")
    print(json.dumps(latest, indent=2))
    raise RuntimeError(
        "SmartThings accepted the commands, but the requested thermostat state "
        "was not verified within 30 seconds."
    )


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("list", help="List thermostat-like SmartThings devices")

    set_parser = subparsers.add_parser(
        "set",
        help="Inspect or set a SmartThings thermostat",
    )
    set_parser.add_argument("--device", required=True)
    set_parser.add_argument(
        "--mode",
        required=True,
        choices=["heat", "cool"],
    )
    set_parser.add_argument(
        "--temperature",
        required=True,
        type=float,
    )
    set_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    token = os.environ.get("SMARTTHINGS_TOKEN")
    if not token:
        print("SMARTTHINGS_TOKEN is not set.", file=sys.stderr)
        return 2

    try:
        if args.action == "list":
            devices = thermostats(token)
            if not devices:
                print("No complete thermostat devices found.")
                return 1
            for device in devices:
                print(
                    json.dumps(
                        {
                            "label": device.get("label"),
                            "device_id": masked_device_id(
                                device.get("deviceId", "")
                            ),
                        }
                    )
                )
            return 0

        set_thermostat(
            token,
            args.device,
            args.mode,
            args.temperature,
            args.dry_run,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
