# ══════════════════════════════════════════════════════════════
# collect_and_save.py
# Read-only data collection from Cisco and FortiGate devices
# ══════════════════════════════════════════════════════════════
#
# SAFETY FEATURES IN THIS SCRIPT:
#   1. DRY_RUN mode    → prints what it WOULD do, touches nothing
#   2. Read-only commands only (show commands, no config changes)
#   3. Credentials from .env (never hardcoded)
#   4. Per-device error handling (one failure won't stop the rest)
#   5. Timestamped output folders (never overwrites previous runs)
#   6. Connection timeout (won't hang forever on unresponsive devices)
#
# ══════════════════════════════════════════════════════════════

import os
import yaml                          # reads inventory.yaml
from datetime import datetime
from dotenv import load_dotenv
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,          # device didn't respond in time
    NetmikoAuthenticationException,   # wrong username or password
)

# ══════════════════════════════════════════════════════════════
# SAFETY SWITCH — set to False only when you're ready
# ══════════════════════════════════════════════════════════════
DRY_RUN = False
# When DRY_RUN = True:
#   - Loads and validates your inventory
#   - Prints every device it WOULD connect to
#   - Prints every command it WOULD run
#   - Makes ZERO network connections
#   - Safe to run anytime, anywhere
#
# When DRY_RUN = False:
#   - Real SSH connections are made
#   - Commands are sent and output is saved

# ══════════════════════════════════════════════════════════════
# SCOPE CONTROL — limit which devices this run touches
# ══════════════════════════════════════════════════════════════
# Options: "cisco"  "fortigate"  "all"
RUN_SCOPE = "all"

# To test on just ONE device first, set this to its IP.
# Set to None to run against all devices in scope.
TEST_SINGLE_HOST = None
# Example: TEST_SINGLE_HOST = "192.168.216.101"

# ══════════════════════════════════════════════════════════════
# COMMANDS — read-only only (no config commands here)
# ══════════════════════════════════════════════════════════════
CISCO_COMMANDS = [
    "show version",
    "show ip interface brief",
    "show inventory",
]

FORTIGATE_COMMANDS = [
    "get system status",
    "get system interface",
]


# ══════════════════════════════════════════════════════════════
# HELPER FUNCTION
# Defined BEFORE the main loop because Python reads files
# top-to-bottom. A function must exist before it can be called.
# ══════════════════════════════════════════════════════════════
def save_error(folder, host, message):
    """Write an error report file for a failed device."""
    filename = os.path.join(folder, f"{host}_ERROR.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Host  : {host}\n")
        f.write(f"Time  : {datetime.now()}\n")
        f.write(f"Error : {message}\n")


# ══════════════════════════════════════════════════════════════
# LOAD CREDENTIALS from .env
# ══════════════════════════════════════════════════════════════
load_dotenv()

USERNAME      = os.getenv("NETWORK_USERNAME")
PASSWORD      = os.getenv("NETWORK_PASSWORD")
ENABLE_SECRET = os.getenv("NETWORK_ENABLE_SECRET")

if not USERNAME or not PASSWORD:
    print("ERROR: Credentials not found in .env file.")
    print("Make sure .env exists and contains NETWORK_USERNAME and NETWORK_PASSWORD")
    exit(1)


# ══════════════════════════════════════════════════════════════
# LOAD INVENTORY from inventory.yaml
# ══════════════════════════════════════════════════════════════
with open('inventory.yaml', 'r', encoding='utf-8') as f:
    inventory = yaml.safe_load(f)
    # yaml.safe_load() reads the YAML file and converts it into
    # a Python dictionary — same structure as the YAML, but in memory

cisco_devices     = inventory.get("cisco_devices", [])
fortigate_devices = inventory.get("fortigate_devices", [])

# Apply scope filter
if RUN_SCOPE == "cisco":
    devices_to_run = cisco_devices
elif RUN_SCOPE == "fortigate":
    devices_to_run = fortigate_devices
else:
    devices_to_run = cisco_devices + fortigate_devices

# Apply single-host filter if set
if TEST_SINGLE_HOST:
    devices_to_run = [d for d in devices_to_run if d["host"] == TEST_SINGLE_HOST]
    if not devices_to_run:
        print(f"ERROR: Host {TEST_SINGLE_HOST} not found in inventory.")
        exit(1)


# ══════════════════════════════════════════════════════════════
# SET UP OUTPUT FOLDER
# ══════════════════════════════════════════════════════════════
timestamp     = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_folder = f"output_{timestamp}"

if not DRY_RUN:
    os.makedirs(output_folder, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# PRINT RUN SUMMARY before doing anything
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("  NETWORK DATA COLLECTION SCRIPT")
print("=" * 60)
if DRY_RUN:
    print("  Mode    : *** DRY RUN - no connections will be made ***")
else:
    print("  Mode    : LIVE - real SSH connections")
print(f"  Scope   : {RUN_SCOPE}")
print(f"  Devices : {len(devices_to_run)}")
print(f"  Output  : {output_folder if not DRY_RUN else 'N/A (dry run)'}")
print("=" * 60)
print()


# ══════════════════════════════════════════════════════════════
# MAIN LOOP — iterate over every device
# ══════════════════════════════════════════════════════════════
results_summary = []   # collect pass/fail here, print at the end

for device_info in devices_to_run:

    host        = device_info["host"]
    port        = device_info.get("port", 22)
    device_type = device_info["device_type"]
    vendor      = device_info["vendor"]
    site        = device_info.get("site", "unknown")

    # Choose the right command list based on vendor
    commands = CISCO_COMMANDS if vendor == "cisco" else FORTIGATE_COMMANDS

    print(f"[{host}]  site={site}  type={device_type}")

    # ── DRY RUN PATH ─────────────────────────────────────────
    if DRY_RUN:
        print(f"  DRY RUN: Would SSH to {host}:{port} as '{USERNAME}'")
        for cmd in commands:
            print(f"  DRY RUN: Would send command: '{cmd}'")
        print(f"  DRY RUN: Would save to: {output_folder}/{host}.txt")
        print()
        results_summary.append({"host": host, "status": "DRY RUN", "error": None})
        continue   # skip to next device — zero network traffic

    # ── LIVE PATH ────────────────────────────────────────────
    conn_params = {
        "device_type":  device_type,
        "host":         host,
        "port":         port,
        "username":     USERNAME,
        "password":     PASSWORD,
        "timeout":      15,     # seconds before giving up on TCP connection
        "auth_timeout": 10,     # seconds to wait for SSH login prompt
    }

    # Cisco needs enable secret; FortiGate does not use enable mode
    if vendor == "cisco" and ENABLE_SECRET:
        conn_params["secret"] = ENABLE_SECRET

    try:
        print(f"  Connecting...", end="", flush=True)
        # flush=True forces the text to appear immediately (Python buffers output)
        connection = ConnectHandler(**conn_params)

        if vendor == "cisco":
            connection.enable()    # enter privileged mode on Cisco

        print(" connected.")

        # Build output text block for this device
        device_output  = "=" * 60 + "\n"
        device_output += f"Host     : {host}\n"
        device_output += f"Site     : {site}\n"
        device_output += f"Type     : {device_type}\n"
        device_output += f"Collected: {datetime.now()}\n"
        device_output += "=" * 60 + "\n\n"

        for cmd in commands:
            print(f"  Running: {cmd}")
            result = connection.send_command(cmd, read_timeout=30)
            device_output += "-" * 40 + "\n"
            device_output += f"Command: {cmd}\n"
            device_output += "-" * 40 + "\n"
            device_output += result + "\n\n"

        connection.disconnect()
        print("  Disconnected.")

        # Save this device's output to its own file
        filename = os.path.join(output_folder, f"{host}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(device_output)

        print(f"  Saved: {filename}\n")
        results_summary.append({"host": host, "status": "SUCCESS", "error": None})

    except NetmikoAuthenticationException:
        msg = "Authentication failed — check credentials in .env"
        print(f"  AUTH ERROR: {msg}\n")
        save_error(output_folder, host, msg)
        results_summary.append({"host": host, "status": "AUTH_FAIL", "error": msg})

    except NetmikoTimeoutException:
        msg = f"Timed out — device unreachable on {host}:{port}"
        print(f"  TIMEOUT: {msg}\n")
        save_error(output_folder, host, msg)
        results_summary.append({"host": host, "status": "TIMEOUT", "error": msg})

    except Exception as error:
        msg = str(error)
        print(f"  ERROR: {msg}\n")
        save_error(output_folder, host, msg)
        results_summary.append({"host": host, "status": "ERROR", "error": msg})


# ══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("  RUN COMPLETE - SUMMARY")
print("=" * 60)

success = [r for r in results_summary if r["status"] == "SUCCESS"]
failed  = [r for r in results_summary if r["status"] not in ("SUCCESS", "DRY RUN")]
dry     = [r for r in results_summary if r["status"] == "DRY RUN"]

if DRY_RUN:
    print(f"  DRY RUN complete. {len(dry)} devices listed.")
    print()
    print("  Recommended next steps:")
    print("  1. Review the device list printed above — does it look right?")
    print("  2. Pick ONE non-critical device to test against")
    print("  3. Set: TEST_SINGLE_HOST = '192.168.x.x'")
    print("  4. Set: DRY_RUN = False")
    print("  5. Run the script — check the output file")
    print("  6. Once confident, set TEST_SINGLE_HOST = None to run all")
else:
    print(f"  Succeeded : {len(success)}")
    print(f"  Failed    : {len(failed)}")
    if failed:
        print()
        print("  Failed devices:")
        for r in failed:
            print(f"    {r['host']:20s}  [{r['status']}] {r['error']}")
    print()
    print(f"  Output folder: {output_folder}/")

print("=" * 60)