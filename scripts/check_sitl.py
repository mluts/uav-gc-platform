#!/usr/bin/env python3

import sys

from uav_gc import link, command
import asyncio


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


async def main():
    check = Check()

    client = link.MavLink.from_args()
    client.start()

    check.log("checking heartbeat...")

    is_up = await client.up()

    check.step("hearbeat", is_up, f"sysid={client.conn.target_system}")

    check.log("checking prearm readiness...")

    cmd = command.ReqSysStatus(client)
    cmd.send()
    msg = await client.wait_for(link.every_pred(link.IsSysStatusMsg, link.SysStatusPrearmReady))

    check.step("prearm check", msg, f"sysid={client.conn.target_system}")


if __name__ == "__main__":
    asyncio.run(main())


# client = mav_client.MAVClient.from_args()
# hb = client.wait_heartbeat()
#
# check.log(f"mavlink_version={client.protocol_version()}")
#
# check.step("hearbeat", hb is not None, f"sysid={client.target_system()}")
#
# check.log("checking prearm readiness...")
#
# check.step("prearm check", client.is_arm_ready(), f"sysid={client.target_system()}")
