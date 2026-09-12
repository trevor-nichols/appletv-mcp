from dataclasses import dataclass

import pytest

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.userspace import open_userspace
from tests.fakes import FakeRsd, fake_session

REMOTE_PAIRING = "pymobiledevice3.remote.tunnel_service"


@dataclass
class _FakePairing:
    remote_identifier: str
    remote_device_model: str
    closed: bool = False

    async def close(self) -> None:
        self.closed = True


async def test_open_userspace_requires_a_configured_udid() -> None:
    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig())
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid" in excinfo.value.detail


async def test_open_userspace_uses_the_matching_apple_tv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phone = _FakePairing("00008101-CCCC", "iPhone14,2")
    tv = _FakePairing("00008110-AAAA", "AppleTV14,1")
    session = fake_session(FakeRsd("00008110-AAAA", "AppleTV14,1"), Transport.USERSPACE)
    connected: list[str] = []

    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        assert udid == "00008110-AAAA"
        assert bonjour_timeout == 3.0
        return [phone, tv]

    async def connect(provider: _FakePairing) -> object:
        connected.append(provider.remote_identifier)
        return session

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)
    monkeypatch.setattr("appletv_screenshot.userspace.session_from_provider", connect)

    result = await open_userspace(SidecarConfig(udid="00008110-AAAA"))

    assert result is session
    assert connected == ["00008110-AAAA"]
    assert phone.closed
    assert not tv.closed


async def test_open_userspace_rejects_a_configured_iphone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phone = _FakePairing("00008101-CCCC", "iPhone14,2")

    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        return [phone]

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)

    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig(udid="00008101-CCCC"))

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "not an Apple TV" in excinfo.value.detail
    assert phone.closed


async def test_open_userspace_with_no_matching_service_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        return []

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)

    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig(udid="00008110-AAAA"))

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "00008110-AAAA is not reachable" in excinfo.value.detail
