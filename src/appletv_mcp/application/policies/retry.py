"""Retry and idempotency policy for Apple TV operations."""

import logging
from collections.abc import Awaitable, Callable

from appletv_mcp.application.ports.apple_tv import AppleTVGateway
from appletv_mcp.domain.enums import OperationKind
from appletv_mcp.domain.errors import (
    AppleTVError,
    CommandTimeoutError,
    DeviceConnectionError,
    DeviceUnreachableError,
    UncertainExecutionError,
)

logger = logging.getLogger(__name__)

_CONNECTION_ERRORS = (DeviceConnectionError, DeviceUnreachableError, CommandTimeoutError)


async def execute[T](
    gateway: AppleTVGateway,
    kind: OperationKind,
    operation_label: str,
    action: Callable[[], Awaitable[T]],
) -> T:
    """Run `action`, reconnecting at most once when the policy allows it."""

    try:
        return await action()
    except _CONNECTION_ERRORS as exc:
        return await _recover(gateway, kind, operation_label, action, exc)


async def _recover[T](
    gateway: AppleTVGateway,
    kind: OperationKind,
    operation_label: str,
    action: Callable[[], Awaitable[T]],
    exc: DeviceConnectionError | DeviceUnreachableError | CommandTimeoutError,
) -> T:
    delivered = getattr(exc, "may_have_been_delivered", False)
    gateway.invalidate()

    if kind is OperationKind.NON_IDEMPOTENT and delivered:
        await gateway.disconnect()
        raise UncertainExecutionError(
            f"The connection was lost after the {operation_label} command may have "
            "been delivered. The command was not retried to avoid executing it twice."
        ) from exc

    logger.info("Reconnecting after %s failed: %s", operation_label, exc.message)
    try:
        await gateway.reconnect()
    except AppleTVError:
        raise
    except Exception as reconnect_error:
        raise exc from reconnect_error

    try:
        return await action()
    except _CONNECTION_ERRORS as retry_error:
        gateway.invalidate()
        await gateway.disconnect()
        raise retry_error from exc
