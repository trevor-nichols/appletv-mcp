# ADR 0001. Screen capture transport and target identity

## Status

Accepted for Apple TV MCP v0.2.

## Problem

`apple_tv_screenshot` is observation, not control. The helper process owns pymobiledevice3 because that library is GPL-3.0-or-later. The MCP package must never import it.

pymobiledevice3 11.12.4 documents `PreferredRsdTunnel` as the no-root DVT path. That class prefers `NativeRemotedTunnel` on macOS and otherwise uses `UserspaceRsdTunnel`. `UserspaceRsdTunnel._create_no_root_tunnel_provider` always calls `create_using_usbmux` first. RemotePairing over bonjour runs only after a USB lockdown session exists and `CoreDeviceProxy` is missing. A Wi-Fi Apple TV never presents usbmux, so that class never reaches RemotePairing. `PreferredRsdTunnel(serial=None)` also captures the first device.

`get_remote_pairing_tunnel_services` browses RemotePairing over bonjour without usbmux. The userspace TUN and dial-plane that `UserspaceRsdTunnel` composes still work once a pairing provider is in hand.

pyatv's stable identifier and the helper's RemoteXPC UDID are different namespaces. Treating them as equal would reject valid pairings or accept the wrong device.

## Shape

The helper offers four transports. `auto` tries native on macOS, then userspace, then tunneld. Other hosts try userspace, then tunneld. Privileged tunneld is last. When every `auto` attempt fails, the helper reports the userspace outcome if userspace ran. Native pairing and userspace pairing are different credential domains. Native pairing does not outrank a later userspace device-not-found or tunnel failure.

The userspace transport browses RemotePairing, selects the configured Apple TV, then attaches `UserspaceTun` and `UserspaceDialPlane`. It does not call `PreferredRsdTunnel` or `UserspaceRsdTunnel`.

Capture requires a configured UDID. After connect, `product_type` must be an Apple TV (`AppleTV*` or `Apple TV*`).

MCP `Settings` does not store a RemoteXPC UDID. SPEC_v0.2 §13 only adds helper `command`, `timeout_seconds`, and `max_image_bytes`. The association is administrative. `appletv-screenshot configure --udid` stores it. `appletv-screenshot identify` prints it. `appletv-mcp doctor` reports it next to the pyatv identifier.

`appletv-mcp configure` rewrites device identity and keeps unrelated fields, including `screen_capture` and `command_timeout_seconds`.

PNG validation walks chunks. It requires IHDR first, at least one IDAT, and a complete IEND. It does not decode pixels or check CRCs.

`appletv-mcp doctor` reads helper `--version` for `contract=N`. A mismatch is an optional FAIL and skips capture. A missing helper remains SKIP.

## Alternatives considered

Wrapping `PreferredRsdTunnel` lost. It still enters `UserspaceRsdTunnel`, so a Wi-Fi Apple TV never reaches RemotePairing, and `serial=None` would capture the first device.

Calling `UserspaceRsdTunnel` directly lost for the same usbmux-first provider.

Making privileged `tunneld` the normal path lost. The docs say it is for particular cases. A one-shot capture should not require a root daemon when userspace RemotePairing works.

Storing the RemoteXPC UDID in MCP `Settings` lost. SPEC_v0.2 §13 has no such field. Copying it into the control profile would mix administrative helper identity with MCP-facing config and invite a false equality with the pyatv identifier.

## Tradeoffs accepted

We attach the userspace TUN after RemotePairing browse instead of calling the upstream wrapper. That keeps deterministic UDID selection and skips usbmux. The TUN and dial-plane still come from pymobiledevice3 11.12.4.

Control identity and observation identity stay independently configured. Doctor shows both so a human can confirm they name the same TV.

## Hardware

No Apple TV was captured while recording this decision. Unit tests lock the policy against fakes and against the installed 11.12.4 sources.
