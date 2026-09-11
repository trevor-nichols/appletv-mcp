"""Instructions advertised to MCP hosts and models."""

SERVER_INSTRUCTIONS = """\
Control the configured Apple TV using semantic tools whenever possible.

Prefer app launching, power, playback, seek, text, and volume tools over remote navigation.

Remote button presses are blind and non-idempotent. The server cannot see the Apple TV \
screen or determine which UI element currently has focus.

The app returned by status is the app associated with currently playing media. Do not \
interpret it as a guaranteed currently visible or foreground app.

Use text entry only when an Apple TV text field is focused.

Do not automatically repeat remote presses after an uncertain failure.
"""
