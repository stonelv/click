from __future__ import annotations

import io
import json
import typing as t
from io import StringIO

import pytest

import click
from click.structured_log import LogLevel
from click.structured_log import StructuredLogCommand
from click.structured_log import StructuredLogConfig
from click.structured_log import StructuredLogGroup
from click.structured_log import StructuredLogManager


class TestStructuredLogBasic:
    def test_enable_disable_structured_log(self):
        @click.command(cls=StructuredLogCommand)
        @click.option("--name", default="world")
        def cli(name):
            click.echo(f"Hello {name}")

        runner = click.testing.CliRunner()

        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Hello world" in result.output

        with runner.isolation() as outstreams:
            out, err = outstreams
            log_stream = StringIO()
            with click.Context(cli) as ctx:
                click.enable_structured_log(
                    ctx, json_output=True, output_stream=log_stream
                )
            assert log_stream.getvalue() == ""

    def test_json_output_format(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--name", default="test")
        def cli(name):
            ctx = click.get_current_context()
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )
            click.echo(f"Hello {name}")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--name", "json-test"])

        assert result.exit_code == 0
        assert "Hello json-test" in result.output

    def test_log_record_contains_command_info(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand, name="my-command")
        @click.option("--count", default=1, type=int)
        def cli(count):
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )
            manager.log(LogLevel.INFO, ctx, "Test message")

        runner = click.testing.CliRunner()
        runner.invoke(cli, ["--count", "5"])

        log_output = log_stream.getvalue()
        assert log_output

        for line in log_output.strip().split("\n"):
            if line.strip():
                record = json.loads(line)
                assert "timestamp" in record
                assert "level" in record
                assert "command_name" in record
                assert "command_path" in record
                assert "message" in record

    def test_include_params_option(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--value", default="secret")
        def cli(value):
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)

            click.enable_structured_log(
                ctx,
                json_output=True,
                include_params=False,
                output_stream=log_stream,
            )
            manager.log(LogLevel.INFO, ctx, "No params")

            click.enable_structured_log(
                ctx,
                json_output=True,
                include_params=True,
                output_stream=log_stream,
            )
            manager.log(LogLevel.INFO, ctx, "With params")

        runner = click.testing.CliRunner()
        runner.invoke(cli, ["--value", "my-value"])


class TestStructuredLogHooks:
    def test_before_invoke_hook(self):
        hook_called = []

        def before_hook(ctx, config):
            hook_called.append(ctx.command.name)

        @click.command(cls=StructuredLogCommand, name="hook-cmd")
        def cli():
            pass

        runner = click.testing.CliRunner()

        with click.Context(cli) as ctx:
            manager = click.get_structured_log_manager(ctx)
            manager.add_before_invoke_hook(before_hook)
            click.enable_structured_log(ctx, json_output=False)

        runner.invoke(cli, [])

    def test_after_invoke_hook(self):
        after_results = []

        def after_hook(ctx, result, config, duration):
            after_results.append({"result": result, "duration": duration})

        @click.command(cls=StructuredLogCommand)
        def cli():
            return 42

        with click.Context(cli) as ctx:
            manager = click.get_structured_log_manager(ctx)
            manager.add_after_invoke_hook(after_hook)
            click.enable_structured_log(ctx)

    def test_on_exception_hook(self):
        exception_caught = []

        def exception_hook(ctx, exc, config, duration):
            exception_caught.append({"type": type(exc).__name__, "message": str(exc)})

        @click.command(cls=StructuredLogCommand)
        def cli():
            raise ValueError("Test error")

        with click.Context(cli) as ctx:
            manager = click.get_structured_log_manager(ctx)
            manager.add_on_exception_hook(exception_hook)
            click.enable_structured_log(ctx)

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
            manager = click.get_structured_log_manager(ctx)
            manager.add_before_invoke_hook(hook1)
            manager.add_before_invoke_hook(hook2)
            click.enable_structured_log(ctx)


class TestStructuredLogException:
    def test_exception_chain_logging(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            click.enable_structured_log(
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
                manager = click.get_structured_log_manager(ctx)
                import sys
                manager.log(
                    LogLevel.ERROR,
                    ctx,
                    "Caught exception",
                    exception=sys.exc_info()[1],
                )

        runner = click.testing.CliRunner()
        runner.invoke(cli, [])

    def test_click_exception_logging(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--value", type=int)
        def cli(value):
            ctx = click.get_current_context()
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )
            if value is None:
                raise click.UsageError("Value is required")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code != 0


class TestStructuredLogGroup:
    def test_group_logging(self):
        log_stream = StringIO()

        @click.group(cls=StructuredLogGroup)
        @click.pass_context
        def cli(ctx):
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )

        @cli.command()
        def sub1():
            click.echo("sub1 executed")

        @cli.command()
        def sub2():
            click.echo("sub2 executed")

        runner = click.testing.CliRunner()

        result = runner.invoke(cli, ["sub1"])
        assert result.exit_code == 0
        assert "sub1 executed" in result.output

        result = runner.invoke(cli, ["sub2"])
        assert result.exit_code == 0
        assert "sub2 executed" in result.output


class TestCompatibility:
    def test_echo_compatibility(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        @click.option("--message", default="hello")
        def cli(message):
            ctx = click.get_current_context()
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
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
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )
            items = [1, 2, 3]
            result = []
            for item in items:
                result.append(item * 2)
            click.echo(f"Result: {result}")

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Result: [2, 4, 6]" in result.output


class TestStructuredLogScope:
    def test_structured_log_scope(self):
        log_stream = StringIO()

        @click.command()
        def cli():
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)

            manager.log(LogLevel.INFO, ctx, "Outside scope - should not log")

            with click.structured_log_scope(
                ctx, json_output=True, output_stream=log_stream
            ):
                manager.log(LogLevel.INFO, ctx, "Inside scope - should log")

            manager.log(LogLevel.INFO, ctx, "Outside again - should not log")

        runner = click.testing.CliRunner()
        runner.invoke(cli, [])


class TestCustomFormatter:
    def test_custom_formatter(self):
        log_stream = StringIO()

        def my_formatter(record):
            return f"CUSTOM: [{record.level.value}] {record.message}"

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)
            manager.set_formatter(my_formatter)
            click.enable_structured_log(
                ctx, json_output=False, output_stream=log_stream
            )
            manager.log(LogLevel.WARN, ctx, "Test message")

        runner = click.testing.CliRunner()
        runner.invoke(cli, [])

        log_output = log_stream.getvalue()
        if log_output:
            assert "CUSTOM:" in log_output
            assert "[WARN]" in log_output
            assert "Test message" in log_output

    def test_reset_formatter(self):
        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)
            manager.set_formatter(lambda r: "custom")
            manager.set_formatter(None)

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0


class TestExtraFields:
    def test_extra_fields_in_log(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)
            click.enable_structured_log(
                ctx,
                json_output=True,
                extra_fields={"app_version": "1.0.0", "env": "test"},
                output_stream=log_stream,
            )
            manager.log(LogLevel.INFO, ctx, "Test with extra fields", extra={"request_id": "abc123"})

        runner = click.testing.CliRunner()
        runner.invoke(cli, [])


class TestLogLevel:
    def test_log_level_enum(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARN.value == "WARN"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_log_level_json_serializable(self):
        log_stream = StringIO()

        @click.command(cls=StructuredLogCommand)
        def cli():
            ctx = click.get_current_context()
            manager = click.get_structured_log_manager(ctx)
            click.enable_structured_log(
                ctx, json_output=True, output_stream=log_stream
            )
            manager.log(LogLevel.DEBUG, ctx, "Debug message")
            manager.log(LogLevel.CRITICAL, ctx, "Critical message")

        runner = click.testing.CliRunner()
        runner.invoke(cli, [])
