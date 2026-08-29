import asyncio

import re
import argparse
import time
from pymavlink import mavutil
from pymavlink.dialects.v20.ardupilotmega import MAVLink_message
from typing import Callable
from functools import reduce

MAV = mavutil.mavlink


class LinkDown(Exception):
    pass


def every_pred(*preds):
    return lambda v: reduce((lambda res, pred: res and pred(v)), preds, True)


IsSysStatusMsg = lambda msg: msg.get_msgId() == MAV.MAVLINK_MSG_ID_SYS_STATUS
SysStatusPrearmReady = lambda msg: (
    msg.onboard_control_sensors_health & MAV.MAV_SYS_STATUS_PREARM_CHECK
)


class MavLink:
    HEARTBEAT_PERIOD = 1.0
    HEARTBEAT_TIMEOUT = 5.0
    WATCHDOG_TIME = 1.0

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

        self.latest: dict[str, tuple] = {}
        self.last_heartbeat_at: float | None = None
        self._hb_seen = asyncio.Event()

        self._listeners: list[tuple[Callable, asyncio.Future]] = []

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

    def protocol_version(self):
        return self.conn.WIRE_PROTOCOL_VERSION

    def start(self):
        loop = asyncio.get_running_loop()
        loop.add_reader(self.conn.port.fileno(), self._on_readable)
        self._started_at = time.monotonic()

    def stop(self):
        asyncio.get_running_loop().remove_reader(self.conn.port.fileno())
        self.conn.close()

    async def up(self, timeout=10):
        async with asyncio.timeout(timeout):
            await self._hb_seen.wait()

        return self._hb_seen.is_set()

    def _on_readable(self):
        while (msg := self.conn.recv_match(blocking=False)) is not None:
            self._dispatch(msg)

    def _dispatch(self, msg: MAVLink_message):
        now = time.monotonic()
        self.latest[msg.get_type()] = (msg, now)

        if msg.get_msgId() == MAV.MAVLINK_MSG_ID_HEARTBEAT:
            self.last_heartbeat_at = now
            self._hb_seen.set()

        if self._listeners:
            for pred, fut in self._listeners:
                if not fut.done() and pred(msg):
                    fut.set_result(msg)

            self._listeners = [(p, f) for p, f in self._listeners if not f.done()]

    # https://mavlink.io/en/messages/common.html#HEARTBEAT
    async def heartbeat_out(self):
        while True:
            self.conn.mav.heartbeat_send(
                MAV.MAV_TYPE_GCS, MAV.MAV_AUTOPILOT_INVALID, 0, 0, MAV.MAV_STATE_ACTIVE
            )
            await asyncio.sleep(self.HEARTBEAT_PERIOD)

    async def watchdog(self):
        while True:
            await asyncio.sleep(self.WATCHDOG_TIME)

            if self._started_at is None:
                raise RuntimeError("Can't start watchhdog before link")

            ref = self.last_heartbeat_at or self._started_at

            if (age := time.monotonic() - ref) > self.HEARTBEAT_TIMEOUT:
                raise LinkDown(f"No heartbeat for {age:.1f}s")

    async def wait_for(self, pred, timeout=5.0):
        fut = asyncio.get_running_loop().create_future()
        self._listeners.append((pred, fut))

        try:
            async with asyncio.timeout(timeout):
                return await fut
        finally:
            if not fut.done():
                fut.cancel()

    # def req_msg(self, msg_id, return_status=True):
    #     cmd = CmdLong(self, MAV.MAV_CMD_REQUEST_MESSAGE, msg_id)
    #
    #     cmd_exec = CommandExecutor(
    #         cmd, self.ack_timeout, self.retries, self.deadline_max
    #     )
    #
    #     return AckStatus.return_or_raise(
    #         cmd_exec.send_and_confirm(), return_status=return_status
    #     )
    #
    # # https://mavlink.io/en/messages/common.html#SYS_STATUS
    # def req_sys_status(self, return_status=True):
    #     return self.req_msg(MAV.MAVLINK_MSG_ID_SYS_STATUS, return_status=return_status)
    #
    # def is_arm_ready(self, wait_timeout=60, return_status=True):
    #     (status, _) = AckStatus.return_or_raise(self.req_sys_status(return_status=return_status))
    #
    #     if status != AckStatus.Accepted:
    #         return False
    #
    #     msg = self.conn.recv_match(
    #         type="SYS_STATUS",
    #         blocking=True,
    #         timeout=wait_timeout,
    #     )
    #
    #     return msg and (
    #         msg.onboard_control_sensors_health & MAV.MAV_SYS_STATUS_PREARM_CHECK
    #     )
