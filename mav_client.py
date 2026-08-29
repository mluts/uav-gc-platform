from pymavlink import mavutil
from dataclasses import dataclass
from typing import Any

# from pymavlink.dialects.v20 import ardupilotmega

import argparse
import re
import time
from enum import Enum, auto

# SITL_SERIAL1 = "tcp:127.0.0.1:5762"
SITL_SERIAL1 = "udpin:127.0.0.1:14550"
MAV = mavutil.mavlink


@dataclass(frozen=True)
class AckMissing:
    name: str

    def description(self):
        return self.name


@dataclass(frozen=True)
class CommandAckMsg:
    msg: Any

    def result(self):
        if self.msg:
            return self.msg.result, MAV.enums["MAV_RESULT"][self.msg.result]
        else:
            return None, AckMissing("No response for COMMAND_ACK")

    def is_in_progress(self) -> bool:
        return self.result()[0] == MAV.MAV_RESULT_IN_PROGRESS

    def is_accepted(self) -> bool:
        return self.result()[0] == MAV.MAV_RESULT_ACCEPTED

    def is_unsuccessful(self) -> bool:
        return not (self.is_in_progress() or self.is_accepted())


class AckStatus(Enum):
    InProgress = (auto(), "Vehicle processes command")
    InProgressTimeout = (auto(), "Deadline reached (slow vehicle processing)")
    Accepted = (auto(), "OK")
    VehicleLost = (auto(), "No response")
    VehicleLostInProgress = (auto(), "No response after processing command")

    Rejected = (auto(), "Rejected for some reason")

    @staticmethod
    def return_or_raise(status_tuple, return_status=True):
        (status, details) = status_tuple

        if return_status:
            return status_tuple

        if status != AckStatus.Accepted:
            raise RuntimeError(
                f"Didn't receive command status, reason: {details.result if details else 'Unknown'}"
            )


@dataclass(frozen=True)
class CmdLong:
    client: "MAVClient"
    cmd_id: int
    p1: float = 0
    p2: float = 0
    p3: float = 0
    p4: float = 0
    p5: float = 0
    p6: float = 0
    p7: float = 0

    def send(self, confirmation: int = 0):
        # print("Sending")
        c = self.client.conn

        c.mav.command_long_send(
            c.target_system,
            c.target_component,
            self.cmd_id,
            confirmation,
            self.p1,
            self.p2,
            self.p3,
            self.p4,
            self.p5,
            self.p6,
            self.p7,
        )

    def recv_ack(self, timeout) -> CommandAckMsg:
        c = self.client.conn

        return CommandAckMsg(
            c.recv_match(
                type="COMMAND_ACK",
                condition=f"COMMAND_ACK.command=={self.cmd_id} and COMMAND_ACK.target_system=={c.source_system} and COMMAND_ACK.target_component=={c.source_component}",
                blocking=True,
                timeout=timeout,
            )
        )


class CommandExecutor:
    ack_status: AckStatus | None
    cmd: CmdLong

    def __init__(self, cmd, ack_timeout=5, retries=3, deadline_max=60):
        self.cmd = cmd
        self.retries = retries
        self.ack_timeout = ack_timeout
        self.ack_status = None
        self.ack_status_details = None
        self.deadline_max = deadline_max

    def send_and_confirm(self) -> tuple[AckStatus, Any]:
        ack = None

        for confirmation in range(self.retries):
            self.cmd.send(confirmation)

            deadline = time.monotonic() + self.ack_timeout

            while (left := deadline - time.monotonic()) > 0:
                ack = self.cmd.recv_ack(left)

                if ack:
                    if ack.is_accepted():
                        self.ack_status = AckStatus.Accepted
                        return (self.ack_status, ack)

                    if ack.is_unsuccessful():
                        self.ack_status = AckStatus.Rejected
                        return (self.ack_status, ack)

                    if ack.is_in_progress():
                        self.ack_status = AckStatus.InProgress

                        if deadline >= self.deadline_max:
                            self.ack_status = AckStatus.InProgressTimeout
                            return (self.ack_status, ack)

                        deadline += self.ack_timeout
                        continue

        if self.ack_status == AckStatus.InProgress:
            self.ack_status = AckStatus.VehicleLostInProgress

        if self.ack_status is None:
            self.ack_status = AckStatus.VehicleLost

        return (self.ack_status, None)


class MAVClient:
    conn: mavutil.mavfile

    def __init__(
        self,
        dev,
        baud=115200,
        wait_timeout=60,
        ack_timeout=10,
        retries=3,
        deadline_max=60,
    ):
        self.conn = mavutil.mavlink_connection(dev, baud=baud)
        self.ack_timeout = ack_timeout
        self.retries = retries
        self.deadline_max = deadline_max
        self.wait_timeout = wait_timeout

    @classmethod
    def from_args(cls):
        parser = argparse.ArgumentParser()
        transport = parser.add_mutually_exclusive_group(required=True)
        transport.add_argument(
            "--tcp",
            type=cls._host_port,
            action="store",
            help="TCP endpoint in the form host:port",
        )

        transport.add_argument(
            "--udp",
            type=cls._host_port,
            action="store",
            help="UDP endpoint in the form host:port",
        )

        transport.add_argument(
            "--serial",
            action="store",
            help="serial device path",
        )
        parser.add_argument(
            "--baud",
            type=int,
            default=None,
            help="serial baud rate (default: 115200)",
        )

        args = parser.parse_args()
        if args.serial:
            baud = args.baud if args.baud is not None else 115200
            if baud <= 0:
                parser.error("--baud must be a positive integer")
            return cls(args.serial, baud=baud)

        if args.baud is not None:
            parser.error("--baud can only be used with --serial")

        if args.tcp:
            return cls(f"tcp:{args.tcp}")

        return cls(f"udpin:{args.udp}")

    @staticmethod
    def _host_port(value):
        if not re.fullmatch(r"[^:]+:\d+", value):
            raise argparse.ArgumentTypeError("must be in the form host:port")

        return value

    # https://mavlink.io/en/messages/common.html#HEARTBEAT
    def wait_heartbeat(self):
        return self.conn.wait_heartbeat(timeout=self.wait_timeout)

    def protocol_version(self):
        return self.conn.WIRE_PROTOCOL_VERSION

    def target_system(self):
        return self.conn.target_system

    def target_component(self):
        return self.conn.target_component

    def req_msg(self, msg_id, return_status=True):
        cmd = CmdLong(self, MAV.MAV_CMD_REQUEST_MESSAGE, msg_id)

        cmd_exec = CommandExecutor(
            cmd, self.ack_timeout, self.retries, self.deadline_max
        )

        return AckStatus.return_or_raise(
            cmd_exec.send_and_confirm(), return_status=return_status
        )

    # https://mavlink.io/en/messages/common.html#SYS_STATUS
    def req_sys_status(self, return_status=True):
        return self.req_msg(MAV.MAVLINK_MSG_ID_SYS_STATUS, return_status=return_status)

    def is_arm_ready(self, wait_timeout=60, return_status=True):
        AckStatus.return_or_raise(self.req_sys_status(return_status=return_status))

        msg = self.conn.recv_match(
            type="SYS_STATUS",
            blocking=True,
            timeout=wait_timeout,
        )

        return msg and (
            msg.onboard_control_sensors_health & MAV.MAV_SYS_STATUS_PREARM_CHECK
        )
