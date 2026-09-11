"""Classify pyatv DeviceModel values without treating every AirPlay device as a TV."""

from enum import StrEnum

from pyatv.const import DeviceModel
from pyatv.interface import DeviceInfo

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice

_NON_APPLE_TV_MODELS = frozenset(
    {
        DeviceModel.HomePod,
        DeviceModel.HomePodMini,
        DeviceModel.HomePodGen2,
        DeviceModel.AirPortExpress,
        DeviceModel.AirPortExpressGen2,
        DeviceModel.Music,
    }
)


class DeviceClass(StrEnum):
    APPLE_TV = "apple_tv"
    UNKNOWN = "unknown"
    OTHER = "other"


def device_model_name(device_info: DeviceInfo) -> str:
    """Return the pyatv 0.18.0 `DeviceModel` member name."""

    return device_info.model.name


def classify_device_model(device_model: str | None) -> DeviceClass:
    """Blacklist known non-TVs; unknown/future models stay selectable with a warning."""

    if device_model is None or device_model == DeviceModel.Unknown.name:
        return DeviceClass.UNKNOWN
    try:
        model = DeviceModel[device_model]
    except KeyError:
        return DeviceClass.UNKNOWN
    if model in _NON_APPLE_TV_MODELS:
        return DeviceClass.OTHER
    return DeviceClass.APPLE_TV


def partition_discovered_devices(
    devices: list[DiscoveredDevice],
) -> tuple[list[DiscoveredDevice], list[DiscoveredDevice], list[DiscoveredDevice]]:
    """Return Apple TVs, unknown-model devices, and known non-TV devices."""

    apple_tvs: list[DiscoveredDevice] = []
    unknowns: list[DiscoveredDevice] = []
    others: list[DiscoveredDevice] = []
    for device in devices:
        kind = classify_device_model(device.device_model)
        if kind is DeviceClass.OTHER:
            others.append(device)
        elif kind is DeviceClass.UNKNOWN:
            unknowns.append(device)
        else:
            apple_tvs.append(device)
    return apple_tvs, unknowns, others
