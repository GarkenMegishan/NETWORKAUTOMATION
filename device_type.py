import os
from dotenv import load_dotenv
from netmiko import ConnectHandler
from netmiko import SSHDetect

load_dotenv()

USERNAME = os.getenv("NETWORK_USERNAME")
PASSWORD = os.getenv("NETWORK_PASSWORD")

if not USERNAME or not PASSWORD:
    print("ERROR: Credentials not found. Check your .env file.")
    exit(1)

device = {
    "device_type": "autodetect",
    "host": "192.168.4.200",
    "login":    USERNAME,      # ← from .env, not hardcoded
    "password":    PASSWORD,      # ← from .env, not hardcoded
    "timeout":     10,            # seconds to wait before giving up
    }

detector = SSHDetect(**device)
best_match = detector.autodetect()

print(best_match)