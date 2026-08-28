#!/usr/bin/env python3

import sys

from pymavlink import mavutil


def step(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"

    print(f"[{status}] {name}" + (f" - {detail if detail else ''}"))

    if not ok:
        sys.exit(1)


conn = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
# https://mavlink.io/en/messages/common.html#HEARTBEAT
hb = conn.wait_heartbeat(timeout=10)

step("hearbeat", hb is not None, f"sysid={conn.target_system}")

ready = False
while not ready:
    # https://mavlink.io/en/messages/common.html#SYS_STATUS
    s = conn.recv_match(type="SYS_STATUS", blocking=True, timeout=5)
    # https://mavlink.io/en/messages/common.html#MAV_SYS_STATUS_SENSOR
    # health ∋ (enabled ∋ present)
    # 1 ok, 0 not ok
    ready = s and (
        s.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
    )

step("prearm check", ready, f"sysid={conn.target_system}")
