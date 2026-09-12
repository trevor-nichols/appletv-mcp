"""Instructions advertised to MCP hosts and models."""

SERVER_INSTRUCTIONS = """\
Control the configured Apple TV using semantic tools whenever possible.

Prefer app launching, power, playback, seek, text, and volume tools over remote navigation.

The server does not continuously observe the Apple TV screen. When screen capture is \
configured, use apple_tv_screenshot to obtain a point-in-time image of the currently \
rendered Apple TV screen. A screenshot may become stale after any subsequent action; \
capture again when current visible state matters.

Remote button presses remain blind and non-idempotent. When using them for UI navigation, \
take screenshots before or after presses to inspect or verify visible state.

Protected DRM video may appear black in screenshots. Do not infer that the TV is off or \
that playback failed solely from a black protected video region.

The app returned by status is the app associated with currently playing media. Do not \
interpret it as a guaranteed currently visible or foreground app.

Use text entry only when an Apple TV text field is focused.

Do not automatically repeat remote presses after an uncertain failure.
"""
