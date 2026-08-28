#!/usr/bin/env python3

import sys

import mav_client


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

check.log("")

client = mav_client.MAVClient(mav_client.SITL_SERIAL1)

check.log("checking heartbeat...")

check.log("")

hb = client.wait_heartbeat()

check.log(f"mavlink_version={client.protocol_version()}")

check.log("")

check.step("hearbeat", hb is not None, f"sysid={client.target_system()}")

check.log("")

check.log("checking prearm readiness...")

check.log("")

check.step("prearm check", client.is_arm_ready(), f"sysid={client.target_system()}")

check.log("")

