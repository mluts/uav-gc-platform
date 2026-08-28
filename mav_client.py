from pymavlink import mavutil

from pymavlink.dialects.v20 import ardupilotmega

SITL_SERIAL1 = "tcp:127.0.0.1:5762"
MAV = mavutil.mavlink


class MAVClient:
    conn: mavutil.mavfile

    def __init__(self, dev, check_timeout=10):
        self.conn = mavutil.mavlink_connection(dev)
        self.__check_timeout = check_timeout
        pass

    # https://mavlink.io/en/messages/common.html#HEARTBEAT
    def wait_heartbeat(self):
        return self.conn.wait_heartbeat(timeout=self.__check_timeout)

    def protocol_version(self):
        return self.conn.WIRE_PROTOCOL_VERSION

    def target_system(self):
        return self.conn.target_system

    def target_component(self):
        return self.conn.target_component

    def cmd_long(
        self,
        cmd_id,
        msg_id,
        params: tuple[int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0),
        confirmation=0,
    ):
        c = self.conn

        c.mav.command_long_send(
            c.target_system, c.target_component, cmd_id, confirmation, msg_id, *params
        )

    # https://mavlink.io/en/messages/common.html#SYS_STATUS
    def req_sys_status(self):
        self.cmd_long(MAV.MAV_CMD_REQUEST_MESSAGE, MAV.MAVLINK_MSG_ID_SYS_STATUS)

        msg = self.conn.recv_match(type="SYS_STATUS", blocking=True, timeout=10)

        assert msg, "no SYS_STATUS received"

        return msg

    def is_arm_ready(self):
        msg = self.req_sys_status()

        return msg and (
            msg.onboard_control_sensors_health & MAV.MAV_SYS_STATUS_PREARM_CHECK
        )
