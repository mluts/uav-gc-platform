#!/usr/bin/env python3

import sys

from pymavlink import mavutil


class Check:
    indent = ""

    def __indent(self):
        print(self.indent, end="")

    def log(self, *msg):
        self.__indent()
        print(*msg)

    def step(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"

        self.__indent()
        print(f"[{status}] {name}" + (f" - {detail if detail else ''}"))

        if not ok:
            sys.exit(1)

        self.indent += " " * 2


check = Check()

check.log("checking heartbeat...")

conn = mavutil.mavlink_connection(
    "tcp:127.0.0.1:5762",
    dialect="ardupilotmega",
)

# https://mavlink.io/en/messages/common.html#HEARTBEAT
hb = conn.wait_heartbeat(timeout=10)

check.log(f"mavlink_version={conn.WIRE_PROTOCOL_VERSION}")

check.step("hearbeat", hb is not None, f"sysid={conn.target_system}")


check.log("checking prearm readiness...")

conn.mav.command_long_send(
    # conn.target_system, conn.target_component, mavutil.mavlink.command_long_send
)

# https://mavlink.io/en/messages/common.html#SYS_STATUS
s = conn.recv_match(type="SYS_STATUS", blocking=True, timeout=10)
# https://mavlink.io/en/messages/common.html#MAV_SYS_STATUS_SENSOR
# health ∋ (enabled ∋ present)
# 1 ok, 0 not ok
ready = s and (
    s.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
)

check.step("prearm check", ready, f"sysid={conn.target_system}")
