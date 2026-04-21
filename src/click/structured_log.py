from __future__ import annotations

import dataclasses
import enum
import json
import sys
import time
import traceback
import typing as t
from collections import abc
from contextlib import contextmanager
from datetime import datetime, timezone

from . import Context
from . import Group
from .core import Command

if t.TYPE_CHECKING:
    from .core import Context


class LogLevel(enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclasses.dataclass
class StructuredLogRecord:
    timestamp: str
    level: LogLevel
    command_name: str | None
    command_path: str | None
    params: dict[str, t.Any]
    message: str
    duration_ms: float | None
    exception: dict[str, t.Any] | None
    extra: dict[str, t.Any]


@dataclasses.dataclass
class StructuredLogConfig:
    enabled: bool = False
    json_output: bool = False
    log_level: LogLevel = LogLevel.INFO
    include_params: bool = True
    include_duration: bool = True
    include_exception_chain: bool = True
    output_stream: t.TextIO = sys.stderr
    indent_json: bool = False
    extra_fields: dict[str, t.Any] | None = None

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "enabled": self.enabled,
            "json_output": self.json_output,
            "log_level": self.log_level.value,
            "include_params": self.include_params,
            "include_duration": self.include_duration,
            "include_exception_chain": self.include_exception_chain,
            "indent_json": self.indent_json,
            "extra_fields": self.extra_fields,
        }


BeforeInvokeHook = t.Callable[["Context", StructuredLogConfig], None]
AfterInvokeHook = t.Callable[["Context", t.Any, StructuredLogConfig, float], None]
OnExceptionHook = t.Callable[
    ["Context", BaseException, StructuredLogConfig, float], None
]
LogFormatter = t.Callable[[StructuredLogRecord], str]


class StructuredLogManager:
    _before_invoke_hooks: list[BeforeInvokeHook]
    _after_invoke_hooks: list[AfterInvokeHook]
    _on_exception_hooks: list[OnExceptionHook]
    _custom_formatter: LogFormatter | None

    def __init__(self) -> None:
        self._before_invoke_hooks = []
        self._after_invoke_hooks = []
        self._on_exception_hooks = []
        self._custom_formatter = None

    def add_before_invoke_hook(self, hook: BeforeInvokeHook) -> None:
        self._before_invoke_hooks.append(hook)

    def add_after_invoke_hook(self, hook: AfterInvokeHook) -> None:
        self._after_invoke_hooks.append(hook)

    def add_on_exception_hook(self, hook: OnExceptionHook) -> None:
        self._on_exception_hooks.append(hook)

    def set_formatter(self, formatter: LogFormatter | None) -> None:
        self._custom_formatter = formatter

    def _trigger_before_invoke(
        self, ctx: Context, config: StructuredLogConfig
    ) -> None:
        for hook in self._before_invoke_hooks:
            try:
                hook(ctx, config)
            except Exception:
                pass

    def _trigger_after_invoke(
        self, ctx: Context, result: t.Any, config: StructuredLogConfig, duration: float
    ) -> None:
        for hook in self._after_invoke_hooks:
            try:
                hook(ctx, result, config, duration)
            except Exception:
                pass

    def _trigger_on_exception(
        self,
        ctx: Context,
        exc: BaseException,
        config: StructuredLogConfig,
        duration: float,
    ) -> None:
        for hook in self._on_exception_hooks:
            try:
                hook(ctx, exc, config, duration)
            except Exception:
                pass

    def _format_exception_chain(
        self, exc: BaseException, include_chain: bool = True
    ) -> dict[str, t.Any]:
        result = {
            "type": type(exc).__name__,
            "module": type(exc).__module__,
            "message": str(exc),
            "traceback": traceback.format_exception(
                type(exc), exc, exc.__traceback__
            ),
        }

        if include_chain and exc.__cause__ is not None:
            result["cause"] = self._format_exception_chain(
                exc.__cause__, include_chain
            )
        elif include_chain and exc.__context__ is not None:
            result["context"] = self._format_exception_chain(
                exc.__context__, include_chain
            )

        return result

    def _make_record(
        self,
        level: LogLevel,
        ctx: Context,
        message: str,
        duration_ms: float | None = None,
        exception: BaseException | None = None,
        extra: dict[str, t.Any] | None = None,
        config: StructuredLogConfig | None = None,
    ) -> StructuredLogRecord:
        config = config or StructuredLogConfig()
        params = ctx.params.copy() if config.include_params else {}

        exc_dict: dict[str, t.Any] | None = None
        if exception is not None and config.include_exception_chain:
            exc_dict = self._format_exception_chain(
                exception, config.include_exception_chain
            )

        extra_fields = config.extra_fields or {}
        if extra:
            extra_fields = {**extra_fields, **extra}

        return StructuredLogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            command_name=getattr(ctx.command, "name", None),
            command_path=ctx.command_path,
            params=_make_json_serializable(params),
            message=message,
            duration_ms=duration_ms,
            exception=exc_dict,
            extra=_make_json_serializable(extra_fields),
        )

    def _default_formatter(self, record: StructuredLogRecord) -> str:
        base = {
            "timestamp": record.timestamp,
            "level": record.level.value,
            "command_name": record.command_name,
            "command_path": record.command_path,
            "message": record.message,
        }

        if record.params:
            base["params"] = record.params
        if record.duration_ms is not None:
            base["duration_ms"] = record.duration_ms
        if record.exception:
            base["exception"] = record.exception
        if record.extra:
            base["extra"] = record.extra

        return base

    def _format_record(
        self, record: StructuredLogRecord, json_output: bool, indent: bool
    ) -> str:
        if self._custom_formatter:
            return self._custom_formatter(record)

        formatted = self._default_formatter(record)

        if json_output:
            indent_val = 2 if indent else None
            return json.dumps(formatted, ensure_ascii=False, indent=indent_val)
        else:
            parts = [
                f"[{record.timestamp}]",
                f"[{record.level.value}]",
            ]
            if record.command_path:
                parts.append(f"[{record.command_path}]")
            parts.append(record.message)

            if record.duration_ms is not None:
                parts.append(f"(duration={record.duration_ms:.2f}ms)")

            return " ".join(parts)

    def log(
        self,
        level: LogLevel,
        ctx: Context,
        message: str,
        duration_ms: float | None = None,
        exception: BaseException | None = None,
        extra: dict[str, t.Any] | None = None,
        config: StructuredLogConfig | None = None,
    ) -> None:
        config = config or _get_log_config(ctx)
        if not config.enabled:
            return

        record = self._make_record(
            level=level,
            ctx=ctx,
            message=message,
            duration_ms=duration_ms,
            exception=exception,
            extra=extra,
            config=config,
        )
        output = self._format_record(
            record, config.json_output, config.indent_json
        )
        print(output, file=config.output_stream)


def _make_json_serializable(obj: t.Any) -> t.Any:
    if isinstance(obj, abc.Mapping):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, abc.Sequence) and not isinstance(obj, (str, bytes)):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, enum.Enum):
        return obj.value
    elif isinstance(obj, (datetime,)):
        return obj.isoformat()
    elif hasattr(obj, "__dict__"):
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)
    else:
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)


META_KEY = "click.structured_log"


def _invoke_with_structured_log(
    ctx: Context,
    invoke_func: t.Callable[[Context], t.Any],
    command_type_label: str,
) -> t.Any:
    config = _get_log_config(ctx)
    manager = get_structured_log_manager(ctx)

    start_time = time.perf_counter()

    try:
        manager._trigger_before_invoke(ctx, config)

        if config.enabled:
            manager.log(
                LogLevel.INFO,
                ctx,
                f"Starting {command_type_label}: {getattr(ctx.command, 'name', 'unknown')}",
                config=config,
            )

        result = invoke_func(ctx)

        duration_ms = (time.perf_counter() - start_time) * 1000

        manager._trigger_after_invoke(ctx, result, config, duration_ms)

        if config.enabled:
            manager.log(
                LogLevel.INFO,
                ctx,
                f"{command_type_label.capitalize()} completed successfully: {getattr(ctx.command, 'name', 'unknown')}",
                duration_ms=duration_ms,
                config=config,
            )

        return result

    except BaseException as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000

        manager._trigger_on_exception(ctx, exc, config, duration_ms)

        if config.enabled:
            is_click_exception = hasattr(exc, "exit_code")
            level = LogLevel.ERROR if is_click_exception else LogLevel.CRITICAL

            manager.log(
                level,
                ctx,
                f"{command_type_label.capitalize()} failed: {type(exc).__name__}: {exc}",
                duration_ms=duration_ms,
                exception=exc,
                config=config,
            )
        raise


def _get_log_config(ctx: Context) -> StructuredLogConfig:
    config = ctx.meta.get(META_KEY)
    if config is None:
        config = StructuredLogConfig()
        ctx.meta[META_KEY] = config
    return config


def _set_log_config(ctx: Context, config: StructuredLogConfig) -> None:
    ctx.meta[META_KEY] = config


def get_structured_log_manager(ctx: Context) -> StructuredLogManager:
    manager = ctx.meta.get(f"{META_KEY}.manager")
    if manager is None:
        manager = StructuredLogManager()
        ctx.meta[f"{META_KEY}.manager"] = manager
    return manager


def enable_structured_log(
    ctx: Context,
    json_output: bool = False,
    log_level: LogLevel = LogLevel.INFO,
    include_params: bool = True,
    include_duration: bool = True,
    include_exception_chain: bool = True,
    output_stream: t.TextIO = sys.stderr,
    indent_json: bool = False,
    extra_fields: dict[str, t.Any] | None = None,
) -> None:
    config = StructuredLogConfig(
        enabled=True,
        json_output=json_output,
        log_level=log_level,
        include_params=include_params,
        include_duration=include_duration,
        include_exception_chain=include_exception_chain,
        output_stream=output_stream,
        indent_json=indent_json,
        extra_fields=extra_fields,
    )
    _set_log_config(ctx, config)


def disable_structured_log(ctx: Context) -> None:
    config = _get_log_config(ctx)
    config.enabled = False


@contextmanager
def structured_log_scope(
    ctx: Context,
    json_output: bool = False,
    log_level: LogLevel = LogLevel.INFO,
    **kwargs: t.Any,
) -> t.Iterator[None]:
    old_config = ctx.meta.get(META_KEY)
    try:
        enable_structured_log(ctx, json_output=json_output, log_level=log_level, **kwargs)
        yield
    finally:
        if old_config is not None:
            ctx.meta[META_KEY] = old_config
        else:
            ctx.meta.pop(META_KEY, None)


class StructuredLogCommand(Command):
    context_class: type[Context] = Context

    def invoke(self, ctx: Context) -> t.Any:
        return _invoke_with_structured_log(
            ctx,
            super().invoke,
            "command",
        )


class StructuredLogGroup(Group):
    context_class: type[Context] = Context

    def invoke(self, ctx: Context) -> t.Any:
        return _invoke_with_structured_log(
            ctx,
            super().invoke,
            "group",
        )
