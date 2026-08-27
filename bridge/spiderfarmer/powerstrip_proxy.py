"""Power-Strip extension for Growstar's command-capable SF bridge.

SF.PS1.3:
- prefers a real PS/PS5/PS10 DOWN subscription;
- otherwise derives DOWN only from an observed PS-family UP topic of the same PID.

SF.PSC1:
- keeps outlet switching on the dedicated Power-Strip command path;
- routes controller modules (light/fan/blower) of a PS-family device over the
  same validated PS-family DOWN topic;
- keeps ordinary GGS/CB controllers delegated to CommandSpiderFarmerProxy.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .command_model import SpiderFarmerCommandError, compile_controller_command
from .command_proxy import CommandSpiderFarmerProxy
from .mqtt_command import build_publish
from .powerstrip_command import (
    SpiderFarmerPowerStripCommandError,
    compile_outlet_power_command,
    is_powerstrip_prefix,
)
from .state_model import parse_topic


_LOG = logging.getLogger("growstar.spiderfarmer.powerstrip")


class PowerStripCommandSpiderFarmerProxy(CommandSpiderFarmerProxy):
    def _subscribed_powerstrip_down_topics(self, controller_id, pid):
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
            if not is_powerstrip_prefix(info.get("prefix")):
                continue
            matches.append(str(topic))

        return sorted(set(matches))

    def _observed_powerstrip_up_topics(self, pid):
        wanted_pid = str(pid or "").strip().upper()
        if not wanted_pid:
            return []

        capture_path = Path(self.capture_path)
        candidates = [capture_path]
        rotated = Path(str(capture_path) + ".1")
        if rotated.exists():
            candidates.append(rotated)

        matches = []

        for candidate in candidates:
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue

            for line in reversed(lines):
                try:
                    row = json.loads(line)
                except (TypeError, ValueError):
                    continue

                if not isinstance(row, dict):
                    continue

                info = parse_topic(row.get("topic"))
                if not info:
                    continue
                if info.get("direction") != "up":
                    continue
                if info.get("pid") != wanted_pid:
                    continue
                if not is_powerstrip_prefix(info.get("prefix")):
                    continue

                matches.append(str(row.get("topic")))

        return list(dict.fromkeys(matches))

    def _is_observed_powerstrip_pid(self, pid):
        return bool(self._observed_powerstrip_up_topics(pid))

    @staticmethod
    def _down_from_observed_up(topic, pid):
        info = parse_topic(topic)
        wanted_pid = str(pid or "").strip().upper()

        if (
            not info
            or info.get("direction") != "up"
            or info.get("pid") != wanted_pid
            or not is_powerstrip_prefix(info.get("prefix"))
        ):
            raise SpiderFarmerPowerStripCommandError(
                "Beobachtetes Power-Strip-UP-Topic ist ungültig"
            )

        prefix = str(info["prefix"]).upper()
        return f"SF/GGS/{prefix}/API/DOWN/{wanted_pid}"

    def _powerstrip_down_topic(self, controller_id, pid):
        subscribed = self._subscribed_powerstrip_down_topics(controller_id, pid)
        if len(subscribed) == 1:
            return subscribed[0]
        if len(subscribed) > 1:
            raise SpiderFarmerPowerStripCommandError(
                "Mehrere aktive Power-Strip-DOWN-Topics gefunden"
            )

        observed_up = self._observed_powerstrip_up_topics(pid)
        prefixes = []
        for topic in observed_up:
            info = parse_topic(topic)
            if info:
                prefixes.append(str(info["prefix"]).upper())

        unique_prefixes = sorted(set(prefixes))
        if len(unique_prefixes) != 1:
            if not unique_prefixes:
                raise SpiderFarmerPowerStripCommandError(
                    "Kein beobachtetes Power-Strip-UP-Topic für diese PID vorhanden"
                )
            raise SpiderFarmerPowerStripCommandError(
                "Power-Strip-Topic-Prefix ist nicht eindeutig"
            )

        for topic in observed_up:
            info = parse_topic(topic)
            if info and str(info["prefix"]).upper() == unique_prefixes[0]:
                derived = self._down_from_observed_up(topic, pid)
                _LOG.warning(
                    "PS DOWN topic derived from observed UP controller=%s pid=%s up=%s down=%s",
                    controller_id,
                    pid,
                    topic,
                    derived,
                )
                return derived

        raise SpiderFarmerPowerStripCommandError(
            "Power-Strip-DOWN-Topic konnte nicht bestimmt werden"
        )

    async def _dispatch_powerstrip_controller(self, request):
        controller_id = str(request.get("controller_id") or "").strip().lower()
        pid = str(request.get("pid") or "").strip().upper()
        module = str(request.get("module") or "").strip()
        setpoints = request.get("setpoints")

        if not controller_id or not pid or not module:
            raise SpiderFarmerPowerStripCommandError(
                "controller_id, pid und module sind erforderlich"
            )

        if module not in {"light", "fan", "blower"}:
            raise SpiderFarmerPowerStripCommandError(
                f"Power-Strip-Controller-Modul {module!r} ist nicht freigegeben"
            )

        writer = self._controller_writers.get(controller_id)
        if writer is None or writer.is_closing():
            raise SpiderFarmerPowerStripCommandError(
                "Spider-Farmer-Power-Strip ist nicht aktiv mit der Bridge verbunden"
            )

        try:
            compiled = compile_controller_command(
                self.capture_path,
                pid=pid,
                module=module,
                setpoints=setpoints,
            )
        except SpiderFarmerCommandError as exc:
            raise SpiderFarmerPowerStripCommandError(str(exc)) from exc

        topic = self._powerstrip_down_topic(controller_id, pid)
        message = json.dumps(
            compiled["payload"],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        writer.write(build_publish(topic, message))
        await writer.drain()

        _LOG.warning(
            "PS CONTROLLER COMMAND sent controller=%s pid=%s module=%s fields=%s topic=%s template=%s",
            controller_id,
            pid,
            module,
            sorted(compiled["changed_fields"]),
            topic,
            compiled.get("observed_at"),
        )

        return {
            "status": "sent",
            "controller_id": controller_id,
            "pid": pid,
            "module": module,
            "topic": topic,
            "changed_fields": compiled["changed_fields"],
            "template_observed_at": compiled.get("observed_at"),
            "diagnostic": "ps_controller_transport",
            "verified": False,
        }

    async def _dispatch_command(self, request):
        if not isinstance(request, dict):
            raise SpiderFarmerPowerStripCommandError(
                "Command request must be an object"
            )

        action = str(request.get("action") or "").strip()

        if action == "set_controller":
            pid = str(request.get("pid") or "").strip().upper()
            if self._is_observed_powerstrip_pid(pid):
                return await self._dispatch_powerstrip_controller(request)
            return await super()._dispatch_command(request)

        if action != "set_powerstrip_outlet":
            return await super()._dispatch_command(request)

        controller_id = str(request.get("controller_id") or "").strip().lower()
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
