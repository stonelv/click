from __future__ import annotations

import io
import json
import sys
import typing as t
from io import StringIO

import pytest

import click
from click import StructuredLogCommand, StructuredLogGroup
from click.structured_log import (
    AfterInvokeHook,
    BeforeInvokeHook,
    LogFormatter,
    LogLevel,
    OnExceptionHook,
    StructuredLogConfig,
    StructuredLogManager,
    StructuredLogRecord,
    disable_structured_log,
    enable_structured_log,
    get_structured_log_manager,
    structured_log_scope,
)


class TestStructuredLogBasic:
    def test_json_output_format(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand, name="json-test-cmd")
        @click.option("--value", default="default-value")
        def cli(value):
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=True,
                include_params=True,
                output_stream=log_stream,
            )
            manager = get_structured_log_manager(ctx)
            manager.log(
                LogLevel.INFO,
                ctx,
                "Test JSON message",
                extra={"custom_field": "custom_value"},
            )

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--value", "my-test-value"])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        assert log_output.strip()

        record = json.loads(log_output.strip())
        assert "timestamp" in record
        assert record["level"] == "INFO"
        assert record["command_name"] == "json-test-cmd"
        assert record["command_path"] == "json-test-cmd"
        assert record["message"] == "Test JSON message"
        assert record["params"]["value"] == "my-test-value"
        assert record["extra"]["custom_field"] == "custom_value"

    def test_plain_text_output(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand, name="plain-cmd")
        def cli():
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=False,
                output_stream=log_stream,
            )
            manager = get_structured_log_manager(ctx)
            manager.log(LogLevel.WARN, ctx, "Warning message")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        assert "[WARN]" in log_output
        assert "plain-cmd" in log_output or "Warning message" in log_output

    def test_enable_disable_structured_log(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)

            enable_structured_log(
                ctx,
                json_output=True,
                output_stream=log_stream,
            )
            manager.log(LogLevel.INFO, ctx, "Before disable")

            disable_structured_log(ctx)
            manager.log(LogLevel.INFO, ctx, "After disable - should not log")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        lines = [l for l in log_output.strip().split("\n") if l.strip()]
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["message"] == "Before disable"

    def test_include_params_option(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--secret-value", default="secret123")
        def cli(secret_value):
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)

            enable_structured_log(
                ctx,
                json_output=True,
                include_params=False,
                output_stream=log_stream,
            )
            manager.log(LogLevel.INFO, ctx, "No params")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--secret-value", "should-not-appear"])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        record = json.loads(log_output.strip())

        assert record.get("params") == {} or "secret-value" not in str(record.get("params", {}))

    def test_extra_fields_in_log(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)
            enable_structured_log(
                ctx,
                json_output=True,
                extra_fields={"app_version": "1.0.0", "env": "test"},
                output_stream=log_stream,
            )
            manager.log(
                LogLevel.INFO,
                ctx,
                "Test with extra fields",
                extra={"request_id": "abc123"},
            )

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        record = json.loads(log_output.strip())

        assert record["extra"]["app_version"] == "1.0.0"
        assert record["extra"]["env"] == "test"
        assert record["extra"]["request_id"] == "abc123"

    def test_log_level_enum(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARN.value == "WARN"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_config_object(self):
        config = StructuredLogConfig(
            enabled=True,
            json_output=True,
            log_level=LogLevel.DEBUG,
            include_params=False,
            include_duration=True,
            include_exception_chain=True,
            indent_json=True,
            extra_fields={"service": "test-service"},
        )

        config_dict = config.to_dict()
        assert config_dict["enabled"] is True
        assert config_dict["json_output"] is True
        assert config_dict["log_level"] == "DEBUG"
        assert config_dict["include_params"] is False
        assert config_dict["include_duration"] is True
        assert config_dict["include_exception_chain"] is True
        assert config_dict["indent_json"] is True
        assert config_dict["extra_fields"] == {"service": "test-service"}


class TestStructuredLogHooks:
    def test_hooks_with_direct_invoke(self):
        hook_results = {
            "before": [],
            "after": [],
        }

        def before_hook(ctx, config):
            hook_results["before"].append(ctx.command.name)

        def after_hook(ctx, result, config, duration):
            hook_results["after"].append({
                "command_name": ctx.command.name,
                "result": result,
                "duration_ms": duration,
            })

        @click.command(cls=StructuredLogCommand, name="hook-test")
        def cli():
            return "hook-result"

        with click.Context(cli) as ctx:
            manager = get_structured_log_manager(ctx)
            manager.add_before_invoke_hook(before_hook)
            manager.add_after_invoke_hook(after_hook)
            enable_structured_log(ctx)

            result = cli.invoke(ctx)

        assert result == "hook-result"
        assert len(hook_results["before"]) == 1
        assert hook_results["before"][0] == "hook-test"
        assert len(hook_results["after"]) == 1
        assert hook_results["after"][0]["command_name"] == "hook-test"
        assert hook_results["after"][0]["result"] == "hook-result"
        assert hook_results["after"][0]["duration_ms"] >= 0

    def test_exception_hook_with_direct_invoke(self):
        exception_results = []

        def exception_hook(ctx, exc, config, duration):
            exception_results.append({
                "command_name": ctx.command.name,
                "exception_type": type(exc).__name__,
                "duration_ms": duration,
            })

        @click.command(cls=StructuredLogCommand, name="error-cmd")
        def cli():
            raise ValueError("Test exception")

        with click.Context(cli) as ctx:
            manager = get_structured_log_manager(ctx)
            manager.add_on_exception_hook(exception_hook)
            enable_structured_log(ctx)

            with pytest.raises(ValueError) as exc_info:
                cli.invoke(ctx)

        assert str(exc_info.value) == "Test exception"
        assert len(exception_results) == 1
        assert exception_results[0]["command_name"] == "error-cmd"
        assert exception_results[0]["exception_type"] == "ValueError"
        assert exception_results[0]["duration_ms"] >= 0

    def test_multiple_hooks(self):
        counter1 = []
        counter2 = []

        def hook1(ctx, config):
            counter1.append(1)

        def hook2(ctx, config):
            counter2.append(1)

        @click.command(cls=StructuredLogCommand)
        def cli():
            pass

        with click.Context(cli) as ctx:
            manager = get_structured_log_manager(ctx)
            manager.add_before_invoke_hook(hook1)
            manager.add_before_invoke_hook(hook2)
            enable_structured_log(ctx)
            cli.invoke(ctx)

        assert len(counter1) == 1
        assert len(counter2) == 1


class TestStructuredLogException:
    def test_exception_chain_logging(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=True,
                include_exception_chain=True,
                output_stream=log_stream,
            )
            try:
                try:
                    raise ValueError("Inner error")
                except ValueError as e:
                    raise RuntimeError("Outer error") from e
            except RuntimeError:
                manager = get_structured_log_manager(ctx)
                exc = sys.exc_info()[1]
                manager.log(
                    LogLevel.ERROR,
                    ctx,
                    "Caught chained exception",
                    exception=exc,
                )
            click.echo("Done")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Done" in result.output

        log_output = log_stream.getvalue()
        assert log_output.strip()

        record = json.loads(log_output.strip())
        assert "exception" in record
        assert record["exception"]["type"] == "RuntimeError"
        assert "cause" in record["exception"]
        assert record["exception"]["cause"]["type"] == "ValueError"
        assert record["exception"]["cause"]["message"] == "Inner error"
        assert "traceback" in record["exception"]

    def test_log_with_duration_ms(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=True,
                include_duration=True,
                output_stream=log_stream,
            )
            manager = get_structured_log_manager(ctx)
            manager.log(
                LogLevel.INFO,
                ctx,
                "Timed operation",
                duration_ms=123.456,
            )

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        record = json.loads(log_output.strip())
        assert record["duration_ms"] == 123.456


class TestStructuredLogGroup:
    def test_group_and_subcommands(self):
        log_stream = StringIO()

        @click.group(cls=StructuredLogGroup)
        @click.pass_context
        def mycli(ctx):
            enable_structured_log(
                ctx,
                json_output=True,
                output_stream=log_stream,
            )
            manager = get_structured_log_manager(ctx)
            manager.log(LogLevel.INFO, ctx, "Group callback")

        @mycli.command()
        def sub1():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)
            manager.log(LogLevel.INFO, ctx, "sub1 executed")
            click.echo("sub1 done")

        @mycli.command()
        @click.argument("name")
        def sub2(name):
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)
            manager.log(LogLevel.INFO, ctx, f"sub2 with {name}")
            click.echo(f"sub2: {name}")

        runner = click.testing.CliRunner()

        result = runner.invoke(mycli, ["sub1"])
        assert result.exit_code == 0
        assert "sub1 done" in result.output

        result = runner.invoke(mycli, ["sub2", "test-name"])
        assert result.exit_code == 0
        assert "sub2: test-name" in result.output

        log_output = log_stream.getvalue()
        lines = [l for l in log_output.strip().split("\n") if l.strip()]
        assert len(lines) >= 3


class TestCompatibility:
    def test_echo_compatibility(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--message", default="hello")
        def cli(message):
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=True,
                output_stream=log_stream,
            )
            click.echo(f"Regular output: {message}")
            click.secho(f"Styled output: {message}", fg="green")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--message", "test-echo"])

        assert result.exit_code == 0
        assert "Regular output: test-echo" in result.output
        assert "Styled output: test-echo" in result.output

    def test_progressbar_compatibility(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            enable_structured_log(
                ctx,
                json_output=True,
                output_stream=log_stream,
            )
            manager = get_structured_log_manager(ctx)
            manager.log(LogLevel.INFO, ctx, "Starting progress")

            with click.progressbar(range(3), label="Processing") as bar:
                for i in bar:
                    manager.log(LogLevel.DEBUG, ctx, f"Item {i}")

            manager.log(LogLevel.INFO, ctx, "Progress done")
            click.echo("Complete")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Complete" in result.output

        log_output = log_stream.getvalue()
        assert "Starting progress" in log_output
        assert "Progress done" in log_output


class TestStructuredLogScope:
    def test_structured_log_scope(self):
        log_stream = StringIO()

        @click.command()
        def cli():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)

            manager.log(LogLevel.INFO, ctx, "Outside scope 1 - should not log")

            with structured_log_scope(
                ctx,
                json_output=True,
                output_stream=log_stream,
                extra_fields={"session": "test"},
            ):
                manager.log(LogLevel.INFO, ctx, "Inside scope 1")
                manager.log(LogLevel.INFO, ctx, "Inside scope 2")

            manager.log(LogLevel.INFO, ctx, "Outside scope 2 - should not log")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        lines = [l for l in log_output.strip().split("\n") if l.strip()]
        assert len(lines) == 2

        for line in lines:
            record = json.loads(line)
            assert record["extra"]["session"] == "test"
            assert "Inside scope" in record["message"]


class TestCustomFormatter:
    def test_custom_formatter(self):
        log_stream = StringIO()

        def my_formatter(record: StructuredLogRecord) -> str:
            return f"CUSTOM_FORMAT: [{record.level.value}] {record.message}"

        @click.command(cls=StructuredLogCommand, name="custom-test")
        def cli():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)
            manager.set_formatter(my_formatter)
            enable_structured_log(
                ctx,
                json_output=False,
                output_stream=log_stream,
            )
            manager.log(LogLevel.WARN, ctx, "Custom warning")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        assert "CUSTOM_FORMAT:" in log_output
        assert "[WARN]" in log_output
        assert "Custom warning" in log_output

    def test_reset_formatter(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = get_structured_log_manager(ctx)

            manager.set_formatter(lambda r: "CUSTOM")
            enable_structured_log(ctx, json_output=False, output_stream=log_stream)
            manager.log(LogLevel.INFO, ctx, "Test 1")

            manager.set_formatter(None)
            manager.log(LogLevel.INFO, ctx, "Test 2")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0

        log_output = log_stream.getvalue()
        assert "CUSTOM" in log_output
        assert "Test 2" in log_output


class TestClickExceptionSemantics:
    def test_click_usage_error_exit_code(self):
        @click.command(cls=StructuredLogCommand)
        @click.option("--value", type=int)
        def cli(value):
            if value is None:
                raise click.UsageError("Value is required")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code != 0
        assert "Value is required" in result.output

    def test_click_bad_parameter_exit_code(self):
        @click.command(cls=StructuredLogCommand)
        @click.option("--value", type=int)
        def cli(value):
            pass

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--value", "not-an-integer"])

        assert result.exit_code != 0

    def test_exception_propagation(self):
        @click.command(cls=StructuredLogCommand)
        def cli():
            raise RuntimeError("Uncaught exception")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code != 0
        assert result.exception is not None
        assert isinstance(result.exception, RuntimeError)
        assert "Uncaught exception" in str(result.exception)
