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
_REPLAY_UNSAFE = {OperationKind.NON_IDEMPOTENT, OperationKind.REPLAY_UNSAFE}


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

    if _is_uncertain(kind, delivered):
        await gateway.disconnect()
        raise _uncertain_error(operation_label) from exc

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
        if _is_uncertain(kind, getattr(retry_error, "may_have_been_delivered", False)):
            await gateway.disconnect()
            raise _uncertain_error(operation_label) from retry_error
        await gateway.disconnect()
        raise retry_error from exc


def _is_uncertain(kind: OperationKind, delivered: bool) -> bool:
    return kind in _REPLAY_UNSAFE and delivered


def _uncertain_error(operation_label: str) -> UncertainExecutionError:
    return UncertainExecutionError(
        f"The connection was lost after the {operation_label} command may have "
        "been delivered. The command was not retried to avoid executing it twice."
    )
