#!/usr/bin/env python
"""Example usage of Click's structured logging feature.

This example demonstrates:
- JSON structured logging
- Hook/callback injection
- Exception chain recording
- Compatibility with echo/progressbar
- Context manager for scoped logging
"""

import json
import sys
from io import StringIO

sys.path.insert(0, '../../src')

import click
from click import StructuredLogCommand, StructuredLogGroup
from click import testing as click_testing
from click.structured_log import (
    AfterInvokeHook,
    BeforeInvokeHook,
    OnExceptionHook,
    LogFormatter,
    LogLevel,
    StructuredLogConfig,
    StructuredLogManager,
    StructuredLogRecord,
    disable_structured_log,
    enable_structured_log,
    get_structured_log_manager,
    structured_log_scope,
)


def example_basic_json_logging():
    """Example: Basic JSON structured logging."""
    print("\n" + "=" * 60)
    print("Example 1: Basic JSON Structured Logging")
    print("=" * 60)

    log_stream = StringIO()

    @click.command(cls=StructuredLogCommand, name='greet')
    @click.option('--name', default='World')
    def greet(name):
        ctx = click.get_current_context()
        enable_structured_log(
            ctx,
            json_output=True,
            include_params=True,
            output_stream=log_stream
        )
        manager = get_structured_log_manager(ctx)
        manager.log(
            LogLevel.INFO,
            ctx,
            f'Greeting {name}!',
            extra={'request_id': 'req-123', 'user_id': 42}
        )
        click.echo(f'Hello, {name}!')

    runner = click_testing.CliRunner()
    result = runner.invoke(greet, ['--name', 'Alice'])

    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output.strip()}")

    log_output = log_stream.getvalue()
    print(f"\nJSON Log output:")
    for line in log_output.strip().split('\n'):
        if line:
            print(json.dumps(json.loads(line), indent=2))

    assert result.exit_code == 0
    assert 'Hello, Alice!' in result.output


def example_hooks():
    """Example: Using hooks/callbacks."""
    print("\n" + "=" * 60)
    print("Example 2: Hooks/Callbacks")
    print("=" * 60)

    hook_results = {
        'before': [],
        'after': [],
        'exception': [],
    }

    def before_hook(ctx, config):
        hook_results['before'].append({
            'command_name': ctx.command.name,
            'config_enabled': config.enabled,
        })
        print(f"[HOOK] Before invoking: {ctx.command.name}")

    def after_hook(ctx, result, config, duration):
        hook_results['after'].append({
            'command_name': ctx.command.name,
            'duration_ms': duration,
        })
        print(f"[HOOK] After invoking: {ctx.command.name} (took {duration:.3f}ms)")

    def exception_hook(ctx, exc, config, duration):
        hook_results['exception'].append({
            'command_name': ctx.command.name,
            'exception_type': type(exc).__name__,
        })
        print(f"[HOOK] Exception in: {ctx.command.name}: {exc}")

    @click.command(cls=StructuredLogCommand, name='process')
    @click.pass_context
    def process_cmd(ctx):
        enable_structured_log(ctx)
        manager = get_structured_log_manager(ctx)
        manager.add_before_invoke_hook(before_hook)
        manager.add_after_invoke_hook(after_hook)
        manager.add_on_exception_hook(exception_hook)
        click.echo('Processing...')
        return 'done'

    runner = click_testing.CliRunner()
    result = runner.invoke(process_cmd, [])

    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output.strip()}")
    print(f"Before hook count: {len(hook_results['before'])}")
    print(f"After hook count: {len(hook_results['after'])}")

    assert result.exit_code == 0


def example_exception_chain():
    """Example: Exception chain logging."""
    print("\n" + "=" * 60)
    print("Example 3: Exception Chain Logging")
    print("=" * 60)

    log_stream = StringIO()

    @click.command(cls=StructuredLogCommand)
    def exception_cmd():
        ctx = click.get_current_context()
        enable_structured_log(
            ctx,
            json_output=True,
            include_exception_chain=True,
            output_stream=log_stream
        )
        try:
            try:
                raise ValueError("Invalid input")
            except ValueError as e:
                raise RuntimeError("Processing failed") from e
        except RuntimeError:
            import sys
            exc = sys.exc_info()[1]
            manager = get_structured_log_manager(ctx)
            manager.log(
                LogLevel.ERROR,
                ctx,
                "Caught chained exception",
                exception=exc
            )
        click.echo("Done")

    runner = click_testing.CliRunner()
    result = runner.invoke(exception_cmd, [])

    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output.strip()}")

    log_output = log_stream.getvalue()
    if log_output.strip():
        record = json.loads(log_output.strip())
        print(f"\nException log:")
        print(f"  Exception type: {record['exception']['type']}")
        print(f"  Message: {record['exception']['message']}")
        if 'cause' in record['exception']:
            print(f"  Caused by: {record['exception']['cause']['type']}: {record['exception']['cause']['message']}")

    assert result.exit_code == 0


def example_progressbar_compatibility():
    """Example: Compatibility with progressbar."""
    print("\n" + "=" * 60)
    print("Example 4: ProgressBar Compatibility")
    print("=" * 60)

    log_stream = StringIO()

    @click.command(cls=StructuredLogCommand)
    def pb_cmd():
        ctx = click.get_current_context()
        enable_structured_log(ctx, json_output=True, output_stream=log_stream)
        manager = get_structured_log_manager(ctx)
        manager.log(LogLevel.INFO, ctx, 'Starting batch processing')

        with click.progressbar(range(5), label='Processing') as bar:
            for i in bar:
                manager.log(LogLevel.DEBUG, ctx, f'Processing item {i}')

        manager.log(LogLevel.INFO, ctx, 'Batch processing completed')
        click.echo('Done!')

    runner = click_testing.CliRunner()
    result = runner.invoke(pb_cmd, [])

    print(f"Exit code: {result.exit_code}")

    log_output = log_stream.getvalue()
    print(f"\nLog messages recorded: {log_output.count('timestamp')}")
    for line in log_output.strip().split('\n'):
        if line:
            record = json.loads(line)
            print(f"  [{record['level']}] {record['message']}")

    assert result.exit_code == 0
    assert 'Done!' in result.output


def example_structured_log_group():
    """Example: Using StructuredLogGroup."""
    print("\n" + "=" * 60)
    print("Example 5: StructuredLogGroup")
    print("=" * 60)

    log_stream = StringIO()

    @click.group(cls=StructuredLogGroup)
    @click.pass_context
    def mycli(ctx):
        enable_structured_log(ctx, json_output=True, output_stream=log_stream)
        manager = get_structured_log_manager(ctx)
        manager.log(LogLevel.INFO, ctx, 'CLI initialized')

    @mycli.command()
    def init():
        ctx = click.get_current_context()
        manager = get_structured_log_manager(ctx)
        manager.log(LogLevel.INFO, ctx, 'Running init command')
        click.echo('Initializing...')

    @mycli.command()
    @click.argument('name')
    def deploy(name):
        ctx = click.get_current_context()
        manager = get_structured_log_manager(ctx)
        manager.log(LogLevel.INFO, ctx, f'Deploying {name}')
        click.echo(f'Deploying {name}...')

    runner = click_testing.CliRunner()

    print("\nTesting 'init' command:")
    result = runner.invoke(mycli, ['init'])
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output.strip()}")

    print("\nTesting 'deploy' command:")
    result = runner.invoke(mycli, ['deploy', 'production'])
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output.strip()}")

    log_output = log_stream.getvalue()
    print(f"\nTotal log entries: {log_output.count('timestamp')}")


def example_scoped_logging():
    """Example: Using structured_log_scope context manager."""
    print("\n" + "=" * 60)
    print("Example 6: Scoped Logging with Context Manager")
    print("=" * 60)

    log_stream = StringIO()

    @click.command()
    def scoped_cmd():
        ctx = click.get_current_context()
        manager = get_structured_log_manager(ctx)

        # Outside scope - no logging
        manager.log(LogLevel.INFO, ctx, 'This will NOT be logged')

        # Enable logging only in this block
        with structured_log_scope(
            ctx,
            json_output=True,
            output_stream=log_stream,
            extra_fields={'session_id': 'session-abc'}
        ):
            manager.log(LogLevel.INFO, ctx, 'Processing started')
            manager.log(LogLevel.DEBUG, ctx, 'Debug info')
            manager.log(LogLevel.INFO, ctx, 'Processing completed')

        # Outside scope again - no logging
        manager.log(LogLevel.INFO, ctx, 'This will also NOT be logged')

        click.echo('Done')

    runner = click_testing.CliRunner()
    result = runner.invoke(scoped_cmd, [])

    print(f"Exit code: {result.exit_code}")

    log_output = log_stream.getvalue()
    lines = [l for l in log_output.strip().split('\n') if l.strip()]
    print(f"\nLog entries inside scope: {len(lines)}")

    for line in lines:
        record = json.loads(line)
        print(f"  [{record['level']}] {record['message']}")
        assert record['extra']['session_id'] == 'session-abc'

    assert result.exit_code == 0
    assert len(lines) == 3


def example_custom_formatter():
    """Example: Using custom log formatter."""
    print("\n" + "=" * 60)
    print("Example 7: Custom Log Formatter")
    print("=" * 60)

    log_stream = StringIO()

    def my_formatter(record: StructuredLogRecord) -> str:
        return (
            f"[{record.timestamp[:19]}] "
            f"[{record.level.value:^7}] "
            f"{record.command_path or 'unknown'}: "
            f"{record.message}"
        )

    @click.command(cls=StructuredLogCommand, name='custom-format')
    def custom_format_cmd():
        ctx = click.get_current_context()
        manager = get_structured_log_manager(ctx)
        manager.set_formatter(my_formatter)
        enable_structured_log(ctx, json_output=False, output_stream=log_stream)
        manager.log(LogLevel.INFO, ctx, 'Custom formatter test')
        manager.log(LogLevel.WARN, ctx, 'Warning message')
        click.echo('Done')

    runner = click_testing.CliRunner()
    result = runner.invoke(custom_format_cmd, [])

    print(f"Exit code: {result.exit_code}")

    log_output = log_stream.getvalue()
    print(f"\nCustom formatted output:")
    for line in log_output.strip().split('\n'):
        if line:
            print(f"  {line}")

    assert result.exit_code == 0
    assert '[ INFO  ]' in log_output
    assert '[ WARN  ]' in log_output


def example_config_object():
    """Example: Using StructuredLogConfig directly."""
    print("\n" + "=" * 60)
    print("Example 8: StructuredLogConfig Object")
    print("=" * 60)

    config = StructuredLogConfig(
        enabled=True,
        json_output=True,
        log_level=LogLevel.DEBUG,
        include_params=False,
        include_duration=True,
        include_exception_chain=True,
        indent_json=True,
        extra_fields={'app_version': '1.0.0', 'env': 'production'},
    )

    print(f"Config settings:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Click Structured Logging Examples")
    print("=" * 60)

    try:
        example_basic_json_logging()
        example_hooks()
        example_exception_chain()
        example_progressbar_compatibility()
        example_structured_log_group()
        example_scoped_logging()
        example_custom_formatter()
        example_config_object()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
