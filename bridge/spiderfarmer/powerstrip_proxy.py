"""Power-Strip extension for Growstar's command-capable SF bridge.

Existing CB controller commands continue to be handled by
CommandSpiderFarmerProxy unchanged. This subclass intercepts only the dedicated
set_powerstrip_outlet action and delegates every other action to the existing
implementation.
"""

from __future__ import annotations

import json
import logging

from .command_proxy import CommandSpiderFarmerProxy
from .mqtt_command import build_publish
from .powerstrip_command import (
    SpiderFarmerPowerStripCommandError,
    compile_outlet_power_command,
)
from .state_model import parse_topic


_LOG = logging.getLogger("growstar.spiderfarmer.powerstrip")


class PowerStripCommandSpiderFarmerProxy(CommandSpiderFarmerProxy):
    def _powerstrip_down_topic(self, controller_id, pid):
        subscriptions = self._controller_subscriptions.get(controller_id, set())
        wanted_pid = str(pid or "").strip().upper()

        matches = []
        for topic in subscriptions:
            info = parse_topic(topic)
            if not info:
                continue
            if info.get("direction") != "down":
                continue
            if info.get("pid") != wanted_pid:
                continue
            if str(info.get("prefix") or "").upper() != "PS":
                continue
            matches.append(str(topic))

        if len(matches) != 1:
            raise SpiderFarmerPowerStripCommandError(
                "Aktives PS-DOWN-Topic konnte nicht eindeutig bestimmt werden"
            )

        return matches[0]

    async def _dispatch_command(self, request):
        if not isinstance(request, dict):
            raise SpiderFarmerPowerStripCommandError(
                "Command request must be an object"
            )

        action = str(request.get("action") or "").strip()
        if action != "set_powerstrip_outlet":
            return await super()._dispatch_command(request)

        controller_id = str(
            request.get("controller_id") or ""
        ).strip().lower()
        pid = str(request.get("pid") or "").strip().upper()
        outlet = request.get("outlet")
        power = request.get("power")

        if not controller_id or not pid:
            raise SpiderFarmerPowerStripCommandError(
                "controller_id und pid sind erforderlich"
            )

        writer = self._controller_writers.get(controller_id)
        if writer is None or writer.is_closing():
            raise SpiderFarmerPowerStripCommandError(
                "Spider-Farmer-Power-Strip ist nicht aktiv mit der Bridge verbunden"
            )

        topic = self._powerstrip_down_topic(controller_id, pid)

        compiled = compile_outlet_power_command(
            self.capture_path,
            pid=pid,
            outlet=outlet,
            power=power,
            topic=topic,
        )

        message = json.dumps(
            compiled["payload"],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        writer.write(build_publish(topic, message))
        await writer.drain()

        _LOG.warning(
            "PS OUTLET COMMAND sent controller=%s pid=%s outlet=%s power=%s topic=%s",
            controller_id,
            pid,
            compiled["outlet"],
            compiled["power"],
            topic,
        )

        return {
            "status": "sent",
            "controller_id": controller_id,
            "pid": pid,
            "module": "outlet",
            "outlet": compiled["outlet"],
            "power": compiled["power"],
            "topic": topic,
            "changed_fields": compiled["changed_fields"],
            "diagnostic": compiled["diagnostic"],
            "verified": False,
        }
