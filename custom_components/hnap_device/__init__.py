# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import functools
import logging
from typing import Dict

import hnap
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import service

from .const import CONF_PLATFORMS, DOMAIN, PLATFORM_BINARY_SENSOR, PLATFORM_SIREN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [PLATFORM_BINARY_SENSOR, PLATFORM_SIREN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HNAP device from a config entry."""

    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    for platform in entry.data[CONF_PLATFORMS]:
        hass.data[DOMAIN][platform] = hass.data[DOMAIN].get(platform, {})

    m = {
        "binary_sensor": hnap.Motion,
        "binary_sensor": hnap.Moisture,
        "camera": hnap.Camera,
        "siren": hnap.Siren,
    }

    client = hnap.soapclient.SoapClient(
        hostname=entry.data[CONF_HOST],
        password=entry.data[CONF_PASSWORD],
        username=entry.data[CONF_USERNAME],
    )
    await hass.async_add_executor_job(client.authenticate)

    # Save device api
    hass.data[DOMAIN][platform][entry.entry_id] = m[platform](client=client)

    # Setup platforms
    hass.config_entries.async_setup_platforms(entry, entry.data[CONF_PLATFORMS])

    # Register service
    async def _handle_service_call(call):
        nonlocal hass
        await handle_service_call(hass, call)

    hass.services.async_register(DOMAIN, "call", _handle_service_call)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        for platform in entry.data[CONF_PLATFORMS]:
            hass.data[DOMAIN][platform].pop(entry.entry_id)

    return unload_ok


async def handle_service_call(hass: HomeAssistant, call: ServiceCall) -> None:
    config_ids = await service.async_extract_config_entry_ids(hass, call)

    for platform in hass.data[DOMAIN]:
        for (config_id, obj) in hass.data[DOMAIN][platform].items():
            if config_id in config_ids:
                fn = functools.partial(
                    _execute_hnap_call,
                    obj,
                    call.data["method"],
                    **call.data.get("parameters", {}),
                )
                await hass.async_add_executor_job(fn)


def _execute_hnap_call(
    target: hnap.devices.Device, method: str, **parameters: Dict[str, str]
) -> None:
    resp = target.client.call(method, **parameters)
    _LOGGER.debug(f"{target}.{method}({parameters}) = {resp}")
