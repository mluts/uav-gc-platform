#!/usr/bin/env python3
import sys

from pymavlink import mavutil

def step(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"

    print(f"[{status}] {name}" + (f" - {detail if detail else ""}"))

    if not ok:
        sys.exit(1)

conn = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
hb = conn.wait_heartbeat(timeout=10)

step("hearbeat", hb is not None, f"sysid={conn.target_system}")
