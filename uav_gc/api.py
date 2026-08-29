import asyncio
import dataclasses
import time
import logging

from aiohttp import web

from .link import MavLink
from .vehicle import Vehicle


def snapshot(vehicle: Vehicle, link: MavLink) -> dict:
    now = time.monotonic()

    hb = vehicle.last_heartbeat

    def group(dc):
        if dc is None:
            return None

        d = dataclasses.asdict(dc)

        d["age_s"] = round(now - d.pop("at"), 2)

        return d

    return {
        "position": group(vehicle.position),
        "attitude": group(vehicle.attitude),
        "batteries": [group(b) for b in vehicle.batteries.values()],
        "mode": vehicle.mav_mode,
        "armed": vehicle.armed,
        "armable": vehicle.armable,
        "position_ok": vehicle.position_ok,
        "link": {
            "status": link.status.name,
            "last_error": link.last_error,
            "heartbeat_age_s": None if hb is None else round(now - hb[1]),
        },
        "ts": time.time(),
    }


class Api:
    def __init__(self, vehicle: Vehicle, link: MavLink):
        self.vehicle = vehicle
        self.link = link

    async def stats(self, _req: web.Request) -> web.Response:
        return web.json_response(snapshot(self.vehicle, self.link))

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/stats", self.stats)
        return app

    async def serve(self, host="127.0.0.1", port=8080):
        runner = web.AppRunner(self.app())

        await runner.setup()
        await web.TCPSite(runner, host, port).start()

        logging.info(f"HTTP Server started on: {host}:{port}")

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
