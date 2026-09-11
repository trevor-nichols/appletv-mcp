"""pyatv DeviceModel classification for configure-time Apple TV filtering."""

from pyatv.const import DeviceModel

from appletv_mcp.infrastructure.pyatv.device_models import (
    DeviceClass,
    classify_device_model,
    partition_discovered_devices,
)
from tests.helpers.fakes import discovered


def test_known_non_tv_models_are_other() -> None:
    for model in (
        DeviceModel.HomePod,
        DeviceModel.HomePodMini,
        DeviceModel.HomePodGen2,
        DeviceModel.AirPortExpress,
        DeviceModel.AirPortExpressGen2,
        DeviceModel.Music,
    ):
        assert classify_device_model(model.name) is DeviceClass.OTHER


def test_apple_tv_and_unknown_models() -> None:
    assert classify_device_model(DeviceModel.Gen4K.name) is DeviceClass.APPLE_TV
    assert classify_device_model(DeviceModel.AppleTVGen1.name) is DeviceClass.APPLE_TV
    assert classify_device_model(DeviceModel.Unknown.name) is DeviceClass.UNKNOWN
    assert classify_device_model(None) is DeviceClass.UNKNOWN
    assert classify_device_model("FutureAppleTV") is DeviceClass.UNKNOWN


def test_partition_splits_scan_results() -> None:
    tv = discovered(name="Living Room", device_model="Gen4K")
    pod = discovered(name="Kitchen", identifier="11:22:33:44:55:66", device_model="HomePod")
    unknown = discovered(name="Mystery", identifier="aa:bb", device_model="Unknown")
    apple_tvs, unknowns, others = partition_discovered_devices([pod, tv, unknown])
    assert apple_tvs == [tv]
    assert unknowns == [unknown]
    assert others == [pod]
