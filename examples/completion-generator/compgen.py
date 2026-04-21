import os
import sys

import click
from click import CompletionItem
from click import generate_completion_script
from click import list_available_shells


def complete_env_vars(ctx, param, incomplete):
    return [k for k in os.environ if incomplete in k]


def complete_users(ctx, param, incomplete):
    users = [
        ("alice", "Administrator"),
        ("bob", "Developer"),
        ("charlie", "Designer"),
        ("david", "Manager"),
        ("eve", "QA Engineer"),
    ]
    return [
        CompletionItem(name, help=desc)
        for name, desc in users
        if incomplete in name or incomplete in desc.lower()
    ]


def complete_files(ctx, param, incomplete):
    import glob
    pattern = incomplete + "*" if incomplete else "*"
    return glob.glob(pattern)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
def cli(verbose, config):
    """A demonstration CLI for Click's completion script generator.

    This CLI demonstrates:
    - Subcommands with nested groups
    - Option value hints (Choice type)
    - Dynamic candidates (shell_complete functions)
    - Completion script generation via 'completion' subcommand
    """
    pass


@cli.command()
@click.argument("filename", type=click.Path())
@click.option("--output", "-o", type=click.Choice(["json", "yaml", "xml", "csv"]), default="json", help="Output format")
@click.option("--encoding", "-e", type=click.Choice(["utf-8", "ascii", "latin-1"]), help="File encoding")
@click.option("--mode", "-m", type=click.Choice(["read", "write", "append"]), default="read", help="File mode")
def read(filename, output, encoding, mode):
    """Read and process a file.

    Demonstrates:
    - Choice type for option values (output, encoding, mode)
    - Path type for arguments
    """
    click.echo(f"Reading {filename} with mode={mode}, encoding={encoding}, output={output}")


@cli.command()
@click.argument("envvar", shell_complete=complete_env_vars)
@click.option("--format", "-f", type=click.Choice(["plain", "json", "shell"]), default="plain", help="Output format")
def env(envvar, format):
    """Display environment variable value.

    Demonstrates:
    - Dynamic completion from environment variables
    - Choice type for format option
    """
    if format == "json":
        import json
        click.echo(json.dumps({"name": envvar, "value": os.environ.get(envvar, "")}))
    elif format == "shell":
        click.echo(f'export {envvar}="{os.environ.get(envvar, "")}"')
    else:
        click.echo(f"{envvar}={os.environ.get(envvar, '')}")


@cli.group()
def user():
    """User management commands.

    Demonstrates nested subcommands.
    """
    pass


@user.command()
@click.argument("username", shell_complete=complete_users)
@click.option("--role", "-r", type=click.Choice(["admin", "developer", "designer", "manager", "qa"]), help="User role")
@click.option("--active/--inactive", default=True, help="User status")
def add(username, role, active):
    """Add a new user.

    Demonstrates:
    - Dynamic completion with help text (users with descriptions)
    - Choice type for role
    - Boolean flag
    """
    status = "active" if active else "inactive"
    click.echo(f"Added user {username} with role={role}, status={status}")


@user.command()
@click.argument("username", shell_complete=complete_users)
def delete(username):
    """Delete an existing user."""
    click.echo(f"Deleted user {username}")


@user.command()
@click.argument("username", shell_complete=complete_users)
def info(username):
    """Show information about a user."""
    click.echo(f"Information for user {username}")


@cli.command(name="completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), required=False)
@click.option("--list", "-l", "list_shells", is_flag=True, help="List all available shells")
@click.option("--prog-name", "-n", help="Program name for the completion script")
@click.option("--install", "-i", is_flag=True, help="Print installation instructions")
def completion_cmd(shell, list_shells, prog_name, install):
    """Generate shell completion script.

    This command demonstrates the new generate_completion_script function.
    It can output completion scripts for bash, zsh, and fish.

    Examples:
      compgen completion bash          # Generate bash completion script
      compgen completion zsh           # Generate zsh completion script
      compgen completion fish          # Generate fish completion script
      compgen completion --list        # List available shells
      compgen completion bash --install # Show installation instructions
    """
    if list_shells:
        shells = list_available_shells()
        click.echo("Available shells:")
        for s in shells:
            click.echo(f"  - {s}")
        return

    if not shell:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return

    try:
        script = generate_completion_script(
            cli=cli,
            shell=shell,
            prog_name=prog_name or "compgen"
        )

        if install:
            click.echo(f"# Installation instructions for {shell}:")
            click.echo("#")
            if shell == "bash":
                click.echo("# Add this to ~/.bashrc:")
                click.echo(f'#   eval "$({prog_name or "compgen"} completion bash)"')
                click.echo("#")
                click.echo("# Or save to a file:")
                click.echo(f'#   {prog_name or "compgen"} completion bash > ~/.compgen-complete.bash')
                click.echo("#   Then add to ~/.bashrc:")
                click.echo("#   . ~/.compgen-complete.bash")
            elif shell == "zsh":
                click.echo("# Add this to ~/.zshrc:")
                click.echo(f'#   eval "$({prog_name or "compgen"} completion zsh)"')
                click.echo("#")
                click.echo("# Or save to a file:")
                click.echo(f'#   {prog_name or "compgen"} completion zsh > ~/.compgen-complete.zsh')
                click.echo("#   Then add to ~/.zshrc:")
                click.echo("#   . ~/.compgen-complete.zsh")
            elif shell == "fish":
                click.echo("# Save to fish completions directory:")
                click.echo(f'#   {prog_name or "compgen"} completion fish > ~/.config/fish/completions/{prog_name or "compgen"}.fish')
            click.echo("#")
            click.echo("# Generated script:")
            click.echo("# " + "=" * 60)

        click.echo(script)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
