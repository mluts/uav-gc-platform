from dataclasses import dataclass
from .link import MavLink
from . import command
from pymavlink import mavutil
import asyncio

MAV = mavutil.mavlink


@dataclass
class Position:
    lat: float
    lon: float  # deg
    alt_msl: float
    alt_rel: float  # m
    vn: float
    ve: float
    vd: float  # m/s NED
    heading: float | None  # deg
    at: float


@dataclass
class Attitude:
    roll: float
    pitch: float
    yaw: float  # rad
    at: float


@dataclass
class Battery:
    voltage: float | None
    current: float | None
    remaining_pct: int | None
    at: float


class Vehicle:
    TELEMETRY_INTERVAL_US: int = 1_000_000

    def __init__(self, link: MavLink):
        self.link = link
        self.position: Position | None = None
        self.attitude: Attitude | None = None
        self.battery: Battery | None = None

        self.link.on(MAV.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, self._on_position)
        self.link.on(MAV.MAVLINK_MSG_ID_ATTITUDE, self._on_attitude)
        self.link.on(MAV.MAVLINK_MSG_ID_SYS_STATUS, self._on_sys_status)
        self.link.on(MAV.MAVLINK_MSG_ID_HEARTBEAT, self._on_heartbeat)

    async def get_message_interval(
        self, msg_id: int, timeout=3.0
    ) -> command.MessageIntervalMsg | None:

        cmd = command.ReqMessageInterval(msg_id, self.link)

        reply = asyncio.create_task(
            self.link.wait_for(
                lambda m: (
                    m.get_msgId() == MAV.MAVLINK_MSG_ID_MESSAGE_INTERVAL
                    and m.message_id == msg_id
                )
            )
        )

        ack = asyncio.create_task(cmd.recv_ack(timeout))

        await asyncio.sleep(0)

        cmd.send()

        (done, _) = await asyncio.wait(
            {reply, ack}, return_when=asyncio.FIRST_COMPLETED
        )

        if ack in done and ack.result().is_unsuccessful():
            reply.cancel()
            return None

        try:
            return command.MessageIntervalMsg(await reply)
        except TimeoutError:
            return None

    async def maybe_set_message_interval(self, msg_id):
        mi = await self.get_message_interval(msg_id)

        if mi is None or not mi.is_enabled():
            cmd = command.SetMessageInterval(
                msg_id, self.TELEMETRY_INTERVAL_US, self.link
            )
            cmd.send()
            ack = await cmd.recv_ack(3.0)

            if ack.is_unsuccessful():
                raise RuntimeError(
                    f"SET_MESSAGE_INTERVAL for MSG {msg_id} refused: {ack.result()}"
                )

    async def start(self):

        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_SYS_STATUS)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_ATTITUDE)
        await self.maybe_set_message_interval(MAV.MAVLINK_MSG_ID_GLOBAL_POSITION_INT)

    def _on_position(self, msg):
        pass

    def _on_attitude(self, msg):
        pass

    def _on_sys_status(self, msg):
        pass

    def _on_heartbeat(self, msg):
        pass
