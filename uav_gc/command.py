from dataclasses import dataclass
from .link import MavLink
from typing import Any
from pymavlink import mavutil

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


@dataclass(frozen=True)
class CmdLong:
    client: MavLink
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

    async def recv_ack(self, timeout) -> CommandAckMsg:
        return CommandAckMsg(
            self.client.wait_for(
                lambda m: (
                    m.get_msgId() == MAV.MAVLINK_MSG_ID_COMMAND_ACK
                    and m.command == self.cmd_id
                ),
                timeout,
            )
        )


ReqSysStatus = lambda client: CmdLong(
    client, MAV.MAV_CMD_REQUEST_MESSAGE, MAV.MAVLINK_MSG_ID_SYS_STATUS
)
