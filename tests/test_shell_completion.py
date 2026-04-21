import textwrap
import warnings
from collections.abc import Mapping

import pytest

import click.shell_completion
from click.core import Argument
from click.core import Command
from click.core import Group
from click.core import Option
from click.shell_completion import add_completion_class
from click.shell_completion import CompletionItem
from click.shell_completion import generate_completion_script
from click.shell_completion import list_available_shells
from click.shell_completion import ShellComplete
from click.types import Choice
from click.types import File
from click.types import Path


def _get_completions(cli, args, incomplete):
    comp = ShellComplete(cli, {}, cli.name, "_CLICK_COMPLETE")
    return comp.get_completions(args, incomplete)


def _get_words(cli, args, incomplete):
    return [c.value for c in _get_completions(cli, args, incomplete)]


def test_command():
    cli = Command("cli", params=[Option(["-t", "--test"])])
    assert _get_words(cli, [], "") == []
    assert _get_words(cli, [], "-") == ["-t", "--test", "--help"]
    assert _get_words(cli, [], "--") == ["--test", "--help"]
    assert _get_words(cli, [], "--t") == ["--test"]
    # -t has been seen, so --test isn't suggested
    assert _get_words(cli, ["-t", "a"], "-") == ["--help"]


def test_group():
    cli = Group("cli", params=[Option(["-a"])], commands=[Command("x"), Command("y")])
    assert _get_words(cli, [], "") == ["x", "y"]
    assert _get_words(cli, [], "-") == ["-a", "--help"]


@pytest.mark.parametrize(
    ("args", "word", "expect"),
    [
        ([], "", ["get"]),
        (["get"], "", ["full"]),
        (["get", "full"], "", ["data"]),
        (["get", "full"], "-", ["--verbose", "--help"]),
        (["get", "full", "data"], "", []),
        (["get", "full", "data"], "-", ["-a", "--help"]),
    ],
)
def test_nested_group(args: list[str], word: str, expect: list[str]) -> None:
    cli = Group(
        "cli",
        commands=[
            Group(
                "get",
                commands=[
                    Group(
                        "full",
                        params=[Option(["--verbose"])],
                        commands=[Command("data", params=[Option(["-a"])])],
                    )
                ],
            )
        ],
    )
    assert _get_words(cli, args, word) == expect


def test_group_command_same_option():
    cli = Group(
        "cli", params=[Option(["-a"])], commands=[Command("x", params=[Option(["-a"])])]
    )
    assert _get_words(cli, [], "-") == ["-a", "--help"]
    assert _get_words(cli, ["-a", "a"], "-") == ["--help"]
    assert _get_words(cli, ["-a", "a", "x"], "-") == ["-a", "--help"]
    assert _get_words(cli, ["-a", "a", "x", "-a", "a"], "-") == ["--help"]


def test_chained():
    cli = Group(
        "cli",
        chain=True,
        commands=[
            Command("set", params=[Option(["-y"])]),
            Command("start"),
            Group("get", commands=[Command("full")]),
        ],
    )
    assert _get_words(cli, [], "") == ["get", "set", "start"]
    assert _get_words(cli, [], "s") == ["set", "start"]
    assert _get_words(cli, ["set", "start"], "") == ["get"]
    # subcommands and parent subcommands
    assert _get_words(cli, ["get"], "") == ["full", "set", "start"]
    assert _get_words(cli, ["get", "full"], "") == ["set", "start"]
    assert _get_words(cli, ["get"], "s") == ["set", "start"]


def test_help_option():
    cli = Group("cli", commands=[Command("with"), Command("no", add_help_option=False)])
    assert _get_words(cli, ["with"], "--") == ["--help"]
    assert _get_words(cli, ["no"], "--") == []


def test_argument_order():
    cli = Command(
        "cli",
        params=[
            Argument(["plain"]),
            Argument(["c1"], type=Choice(["a1", "a2", "b"])),
            Argument(["c2"], type=Choice(["c1", "c2", "d"])),
        ],
    )
    # first argument has no completions
    assert _get_words(cli, [], "") == []
    assert _get_words(cli, [], "a") == []
    # first argument filled, now completion can happen
    assert _get_words(cli, ["x"], "a") == ["a1", "a2"]
    assert _get_words(cli, ["x", "b"], "d") == ["d"]


def test_argument_default():
    cli = Command(
        "cli",
        add_help_option=False,
        params=[
            Argument(["a"], type=Choice(["a"]), default="a"),
            Argument(["b"], type=Choice(["b"]), default="b"),
        ],
    )
    assert _get_words(cli, [], "") == ["a"]
    assert _get_words(cli, ["a"], "b") == ["b"]
    # ignore type validation
    assert _get_words(cli, ["x"], "b") == ["b"]


def test_type_choice():
    cli = Command("cli", params=[Option(["-c"], type=Choice(["a1", "a2", "b"]))])
    assert _get_words(cli, ["-c"], "") == ["a1", "a2", "b"]
    assert _get_words(cli, ["-c"], "a") == ["a1", "a2"]
    assert _get_words(cli, ["-c"], "a2") == ["a2"]


def test_choice_special_characters():
    cli = Command("cli", params=[Option(["-c"], type=Choice(["!1", "!2", "+3"]))])
    assert _get_words(cli, ["-c"], "") == ["!1", "!2", "+3"]
    assert _get_words(cli, ["-c"], "!") == ["!1", "!2"]
    assert _get_words(cli, ["-c"], "!2") == ["!2"]


def test_choice_conflicting_prefix():
    cli = Command(
        "cli",
        params=[
            Option(["-c"], type=Choice(["!1", "!2", "+3"])),
            Option(["+p"], is_flag=True),
        ],
    )
    assert _get_words(cli, ["-c"], "") == ["!1", "!2", "+3"]
    assert _get_words(cli, ["-c"], "+") == ["+p"]


def test_option_count():
    cli = Command("cli", params=[Option(["-c"], count=True)])
    assert _get_words(cli, ["-c"], "") == []
    assert _get_words(cli, ["-c"], "-") == ["--help"]


def test_option_optional():
    cli = Command(
        "cli",
        add_help_option=False,
        params=[
            Option(["--name"], is_flag=False, flag_value="value"),
            Option(["--flag"], is_flag=True),
        ],
    )
    assert _get_words(cli, ["--name"], "") == []
    assert _get_words(cli, ["--name"], "-") == ["--flag"]
    assert _get_words(cli, ["--name", "--flag"], "-") == []


@pytest.mark.parametrize(
    ("type", "expect"),
    [(File(), "file"), (Path(), "file"), (Path(file_okay=False), "dir")],
)
def test_path_types(type, expect):
    cli = Command("cli", params=[Option(["-f"], type=type)])
    out = _get_completions(cli, ["-f"], "ab")
    assert len(out) == 1
    c = out[0]
    assert c.value == "ab"
    assert c.type == expect


def test_absolute_path():
    cli = Command("cli", params=[Option(["-f"], type=Path())])
    out = _get_completions(cli, ["-f"], "/ab")
    assert len(out) == 1
    c = out[0]
    assert c.value == "/ab"


def test_option_flag():
    cli = Command(
        "cli",
        add_help_option=False,
        params=[
            Option(["--on/--off"]),
            Argument(["a"], type=Choice(["a1", "a2", "b"])),
        ],
    )
    assert _get_words(cli, [], "--") == ["--on", "--off"]
    # flag option doesn't take value, use choice argument
    assert _get_words(cli, ["--on"], "a") == ["a1", "a2"]


def test_flag_option_with_nargs_option():
    cli = Command(
        "cli",
        add_help_option=False,
        params=[
            Argument(["a"], type=Choice(["a1", "a2", "b"])),
            Option(["--flag"], is_flag=True),
            Option(["-c"], type=Choice(["p", "q"]), nargs=2),
        ],
    )
    assert _get_words(cli, ["a1", "--flag", "-c"], "") == ["p", "q"]


def test_option_custom():
    def custom(ctx, param, incomplete):
        return [incomplete.upper()]

    cli = Command(
        "cli",
        params=[
            Argument(["x"]),
            Argument(["y"]),
            Argument(["z"], shell_complete=custom),
        ],
    )
    assert _get_words(cli, ["a", "b"], "") == [""]
    assert _get_words(cli, ["a", "b"], "c") == ["C"]


def test_option_multiple():
    cli = Command(
        "type",
        params=[Option(["-m"], type=Choice(["a", "b"]), multiple=True), Option(["-f"])],
    )
    assert _get_words(cli, ["-m"], "") == ["a", "b"]
    assert "-m" in _get_words(cli, ["-m", "a"], "-")
    assert _get_words(cli, ["-m", "a", "-m"], "") == ["a", "b"]
    # used single options aren't suggested again
    assert "-c" not in _get_words(cli, ["-c", "f"], "-")


def test_option_nargs():
    cli = Command("cli", params=[Option(["-c"], type=Choice(["a", "b"]), nargs=2)])
    assert _get_words(cli, ["-c"], "") == ["a", "b"]
    assert _get_words(cli, ["-c", "a"], "") == ["a", "b"]
    assert _get_words(cli, ["-c", "a", "b"], "") == []


def test_argument_nargs():
    cli = Command(
        "cli",
        params=[
            Argument(["x"], type=Choice(["a", "b"]), nargs=2),
            Argument(["y"], type=Choice(["c", "d"]), nargs=-1),
            Option(["-z"]),
        ],
    )
    assert _get_words(cli, [], "") == ["a", "b"]
    assert _get_words(cli, ["a"], "") == ["a", "b"]
    assert _get_words(cli, ["a", "b"], "") == ["c", "d"]
    assert _get_words(cli, ["a", "b", "c"], "") == ["c", "d"]
    assert _get_words(cli, ["a", "b", "c", "d"], "") == ["c", "d"]
    assert _get_words(cli, ["a", "-z", "1"], "") == ["a", "b"]
    assert _get_words(cli, ["a", "-z", "1", "b"], "") == ["c", "d"]


def test_double_dash():
    cli = Command(
        "cli",
        add_help_option=False,
        params=[
            Option(["--opt"]),
            Argument(["name"], type=Choice(["name", "--", "-o", "--opt"])),
        ],
    )
    assert _get_words(cli, [], "-") == ["--opt"]
    assert _get_words(cli, ["value"], "-") == ["--opt"]
    assert _get_words(cli, [], "") == ["name", "--", "-o", "--opt"]
    assert _get_words(cli, ["--"], "") == ["name", "--", "-o", "--opt"]


def test_hidden():
    cli = Group(
        "cli",
        commands=[
            Command(
                "hidden",
                add_help_option=False,
                hidden=True,
                params=[
                    Option(["-a"]),
                    Option(["-b"], type=Choice(["a", "b"]), hidden=True),
                ],
            )
        ],
    )
    assert "hidden" not in _get_words(cli, [], "")
    assert "hidden" not in _get_words(cli, [], "hidden")
    assert _get_words(cli, ["hidden"], "-") == ["-a"]
    assert _get_words(cli, ["hidden", "-b"], "") == ["a", "b"]


def test_add_different_name():
    cli = Group("cli", commands={"renamed": Command("original")})
    words = _get_words(cli, [], "")
    assert "renamed" in words
    assert "original" not in words


def test_completion_item_data():
    c = CompletionItem("test", a=1)
    assert c.a == 1
    assert c.b is None


@pytest.fixture()
def _patch_for_completion(monkeypatch):
    monkeypatch.setattr(
        "click.shell_completion.BashComplete._check_version", lambda self: True
    )


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
@pytest.mark.usefixtures("_patch_for_completion")
def test_full_source(runner, shell):
    cli = Group("cli", commands=[Command("a"), Command("b")])
    result = runner.invoke(cli, env={"_CLI_COMPLETE": f"{shell}_source"})
    assert f"_CLI_COMPLETE={shell}_complete" in result.output


@pytest.mark.parametrize(
    ("shell", "env", "expect"),
    [
        ("bash", {"COMP_WORDS": "", "COMP_CWORD": "0"}, "plain,a\nplain,b\n"),
        ("bash", {"COMP_WORDS": "a b", "COMP_CWORD": "1"}, "plain,b\n"),
        ("zsh", {"COMP_WORDS": "", "COMP_CWORD": "0"}, "plain\na\n_\nplain\nb\nbee\n"),
        ("zsh", {"COMP_WORDS": "a b", "COMP_CWORD": "1"}, "plain\nb\nbee\n"),
        ("fish", {"COMP_WORDS": "", "COMP_CWORD": ""}, "plain,a\nplain,b\tbee\n"),
        ("fish", {"COMP_WORDS": "a b", "COMP_CWORD": "b"}, "plain,b\tbee\n"),
        ("fish", {"COMP_WORDS": 'a "b', "COMP_CWORD": '"b'}, "plain,b\tbee\n"),
    ],
)
@pytest.mark.usefixtures("_patch_for_completion")
def test_full_complete(runner, shell, env, expect):
    cli = Group("cli", commands=[Command("a"), Command("b", help="bee")])
    env["_CLI_COMPLETE"] = f"{shell}_complete"
    result = runner.invoke(cli, env=env)
    assert result.output == expect


@pytest.mark.parametrize(
    ("env", "expect"),
    [
        (
            {"COMP_WORDS": "", "COMP_CWORD": "0"},
            textwrap.dedent(
                """\
                    plain
                    a
                    _
                    plain
                    b
                    bee
                    plain
                    c\\:d
                    cee:dee
                    plain
                    c:e
                    _
                """
            ),
        ),
        (
            {"COMP_WORDS": "a c", "COMP_CWORD": "1"},
            textwrap.dedent(
                """\
                    plain
                    c\\:d
                    cee:dee
                    plain
                    c:e
                    _
                """
            ),
        ),
        (
            {"COMP_WORDS": "a c:", "COMP_CWORD": "1"},
            textwrap.dedent(
                """\
                    plain
                    c\\:d
                    cee:dee
                    plain
                    c:e
                    _
                """
            ),
        ),
    ],
)
@pytest.mark.usefixtures("_patch_for_completion")
def test_zsh_full_complete_with_colons(
    runner, env: Mapping[str, str], expect: str
) -> None:
    cli = Group(
        "cli",
        commands=[
            Command("a"),
            Command("b", help="bee"),
            Command("c:d", help="cee:dee"),
            Command("c:e"),
        ],
    )
    result = runner.invoke(
        cli,
        env={
            **env,
            "_CLI_COMPLETE": "zsh_complete",
        },
    )
    assert result.output == expect


@pytest.mark.usefixtures("_patch_for_completion")
def test_context_settings(runner):
    def complete(ctx, param, incomplete):
        return ctx.obj["choices"]

    cli = Command("cli", params=[Argument("x", shell_complete=complete)])
    result = runner.invoke(
        cli,
        obj={"choices": ["a", "b"]},
        env={"COMP_WORDS": "", "COMP_CWORD": "0", "_CLI_COMPLETE": "bash_complete"},
    )
    assert result.output == "plain,a\nplain,b\n"


@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
def test_choice_case_sensitive(value, expect):
    cli = Command(
        "cli",
        params=[Option(["-a"], type=Choice(["Au", "al", "Bc"], case_sensitive=value))],
    )
    completions = _get_words(cli, ["-a"], "a")
    assert completions == expect


@pytest.fixture()
def _restore_available_shells(tmpdir):
    prev_available_shells = click.shell_completion._available_shells.copy()
    click.shell_completion._available_shells.clear()
    yield
    click.shell_completion._available_shells.clear()
    click.shell_completion._available_shells.update(prev_available_shells)


@pytest.mark.usefixtures("_restore_available_shells")
def test_add_completion_class():
    # At first, "mysh" is not in available shells
    assert "mysh" not in click.shell_completion._available_shells

    class MyshComplete(ShellComplete):
        name = "mysh"
        source_template = "dummy source"

    # "mysh" still not in available shells because it is not registered
    assert "mysh" not in click.shell_completion._available_shells

    # Adding a completion class should return that class
    assert add_completion_class(MyshComplete) is MyshComplete

    # Now, "mysh" is finally in available shells
    assert "mysh" in click.shell_completion._available_shells
    assert click.shell_completion._available_shells["mysh"] is MyshComplete


@pytest.mark.usefixtures("_restore_available_shells")
def test_add_completion_class_with_name():
    # At first, "mysh" is not in available shells
    assert "mysh" not in click.shell_completion._available_shells
    assert "not_mysh" not in click.shell_completion._available_shells

    class MyshComplete(ShellComplete):
        name = "not_mysh"
        source_template = "dummy source"

    # "mysh" and "not_mysh" are still not in available shells because
    # it is not registered yet
    assert "mysh" not in click.shell_completion._available_shells
    assert "not_mysh" not in click.shell_completion._available_shells

    # Adding a completion class should return that class.
    # Because we are using the "name" parameter, the name isn't taken
    # from the class.
    assert add_completion_class(MyshComplete, name="mysh") is MyshComplete

    # Now, "mysh" is finally in available shells
    assert "mysh" in click.shell_completion._available_shells
    assert "not_mysh" not in click.shell_completion._available_shells
    assert click.shell_completion._available_shells["mysh"] is MyshComplete


@pytest.mark.usefixtures("_restore_available_shells")
def test_add_completion_class_decorator():
    # At first, "mysh" is not in available shells
    assert "mysh" not in click.shell_completion._available_shells

    @add_completion_class
    class MyshComplete(ShellComplete):
        name = "mysh"
        source_template = "dummy source"

    # Using `add_completion_class` as a decorator adds the new shell immediately
    assert "mysh" in click.shell_completion._available_shells
    assert click.shell_completion._available_shells["mysh"] is MyshComplete


# Don't make the ResourceWarning give an error
@pytest.mark.filterwarnings("default")
def test_files_closed(runner) -> None:
    with runner.isolated_filesystem():
        config_file = "foo.txt"
        with open(config_file, "w") as f:
            f.write("bar")

        @click.group()
        @click.option(
            "--config-file",
            default=config_file,
            type=click.File(mode="r"),
        )
        @click.pass_context
        def cli(ctx, config_file):
            pass

        with warnings.catch_warnings(record=True) as current_warnings:
            assert not current_warnings, "There should be no warnings to start"
            _get_completions(cli, args=[], incomplete="")
            assert not current_warnings, "There should be no warnings after either"


class TestGenerateCompletionScript:
    """Tests for the generate_completion_script function."""

    def test_list_available_shells(self):
        """Test that list_available_shells returns the supported shells."""
        shells = list_available_shells()
        assert isinstance(shells, list)
        assert "bash" in shells
        assert "zsh" in shells
        assert "fish" in shells

    def test_generate_bash_script(self):
        """Test generating a bash completion script."""
        @click.group()
        def cli():
            pass

        script = generate_completion_script(cli, "bash", "mycli")
        assert isinstance(script, str)
        assert "complete" in script
        assert "mycli" in script
        assert "_MYCLI_COMPLETE" in script

    def test_generate_zsh_script(self):
        """Test generating a zsh completion script."""
        @click.group()
        def cli():
            pass

        script = generate_completion_script(cli, "zsh", "mycli")
        assert isinstance(script, str)
        assert "#compdef" in script
        assert "mycli" in script
        assert "_MYCLI_COMPLETE" in script

    def test_generate_fish_script(self):
        """Test generating a fish completion script."""
        @click.group()
        def cli():
            pass

        script = generate_completion_script(cli, "fish", "mycli")
        assert isinstance(script, str)
        assert "function" in script
        assert "complete" in script
        assert "mycli" in script
        assert "_MYCLI_COMPLETE" in script

    def test_invalid_shell_raises_error(self):
        """Test that an invalid shell raises ValueError."""
        @click.group()
        def cli():
            pass

        with pytest.raises(ValueError) as exc_info:
            generate_completion_script(cli, "invalid_shell", "mycli")

        assert "Unsupported shell" in str(exc_info.value)
        assert "invalid_shell" in str(exc_info.value)

    def test_default_prog_name(self):
        """Test that prog_name defaults to cli.name."""
        @click.group()
        @click.argument("name")
        def mytool():
            pass

        script = generate_completion_script(mytool, "bash")
        assert "mytool" in script
        assert "_MYTOOL_COMPLETE" in script

    def test_default_prog_name_none(self):
        """Test that prog_name defaults to 'cli' when cli.name is None."""
        cli = click.Command(None)
        script = generate_completion_script(cli, "bash")
        assert "cli" in script
        assert "_CLI_COMPLETE" in script

    def test_custom_complete_var(self):
        """Test using a custom complete_var."""
        @click.group()
        def cli():
            pass

        script = generate_completion_script(
            cli, "bash", "mycli", complete_var="_CUSTOM_VAR"
        )
        assert "_CUSTOM_VAR" in script
        assert "_MYCLI_COMPLETE" not in script

    def test_with_subcommands(self):
        """Test generating completion script for CLI with subcommands."""
        @click.group()
        def cli():
            pass

        @cli.command()
        @click.option("--name", help="Name option")
        def sub1(name):
            pass

        @cli.command()
        def sub2():
            pass

        script = generate_completion_script(cli, "bash", "mycli")
        assert isinstance(script, str)
        assert "mycli" in script

    def test_with_choice_options(self):
        """Test generating completion script for CLI with Choice options."""
        @click.command()
        @click.option("--format", type=click.Choice(["json", "yaml", "xml"]))
        def cli(format):
            pass

        script = generate_completion_script(cli, "bash", "mycli")
        assert isinstance(script, str)

    def test_with_dynamic_completion(self):
        """Test generating completion script for CLI with dynamic completion."""
        def complete_things(ctx, param, incomplete):
            return ["apple", "banana", "cherry"]

        @click.command()
        @click.argument("thing", shell_complete=complete_things)
        def cli(thing):
            pass

        script = generate_completion_script(cli, "bash", "mycli")
        assert isinstance(script, str)

    @pytest.mark.usefixtures("_patch_for_completion")
    def test_matches_env_var_method(self, runner):
        """Test that generate_completion_script matches the env var method."""
        @click.group()
        def cli():
            pass

        generated = generate_completion_script(cli, "bash", "cli")

        result = runner.invoke(cli, env={"_CLI_COMPLETE": "bash_source"})

        assert generated.rstrip("\n") == result.output.rstrip("\n")

    @pytest.mark.parametrize(
        ("prog_name", "expected_var"),
        [
            ("mycli", "_MYCLI_COMPLETE"),
            ("my-cli", "_MY_CLI_COMPLETE"),
            ("my.cli", "_MY_CLI_COMPLETE"),
            ("my-cli.app", "_MY_CLI_APP_COMPLETE"),
            ("foo-bar.baz-qux", "_FOO_BAR_BAZ_QUX_COMPLETE"),
        ],
    )
    @pytest.mark.usefixtures("_patch_for_completion")
    def test_prog_name_special_chars_complete_var(self, runner, prog_name, expected_var):
        """Test that prog_name with -/. generates correct complete_var.

        This ensures generate_completion_script uses the same complete_var
        calculation as _main_shell_completion in the existing env var method.
        """
        @click.group()
        def cli():
            pass

        generated = generate_completion_script(cli, "bash", prog_name)
        assert expected_var in generated

        result = runner.invoke(
            cli,
            env={expected_var: "bash_source"},
            prog_name=prog_name,
        )

        assert generated.rstrip("\n") == result.output.rstrip("\n")

    @pytest.mark.usefixtures("_patch_for_completion")
    def test_prog_name_with_dash_matches_env_var(self, runner):
        """Test prog_name with hyphen: my-cli should use _MY_CLI_COMPLETE."""
        @click.group()
        def cli():
            pass

        prog_name = "my-cli"
        expected_var = "_MY_CLI_COMPLETE"

        generated = generate_completion_script(cli, "bash", prog_name)
        assert expected_var in generated
        assert "my-cli" in generated

        result = runner.invoke(
            cli,
            env={expected_var: "bash_source"},
            prog_name=prog_name,
        )
        assert generated.rstrip("\n") == result.output.rstrip("\n")

    @pytest.mark.usefixtures("_patch_for_completion")
    def test_prog_name_with_dot_matches_env_var(self, runner):
        """Test prog_name with dot: my.cli should use _MY_CLI_COMPLETE."""
        @click.group()
        def cli():
            pass

        prog_name = "my.cli"
        expected_var = "_MY_CLI_COMPLETE"

        generated = generate_completion_script(cli, "bash", prog_name)
        assert expected_var in generated
        assert "my.cli" in generated

        result = runner.invoke(
            cli,
            env={expected_var: "bash_source"},
            prog_name=prog_name,
        )
        assert generated.rstrip("\n") == result.output.rstrip("\n")


class TestDemoCLI:
    """Tests for the demo CLI features (subcommands, choice options, dynamic completion)."""

    def test_subcommand_completion(self):
        """Test that subcommands are properly completed."""
        @click.group()
        def cli():
            pass

        @cli.command()
        def init():
            pass

        @cli.command()
        def status():
            pass

        completions = _get_words(cli, [], "")
        assert "init" in completions
        assert "status" in completions

    def test_choice_option_completion(self):
        """Test that Choice option values are properly completed."""
        cli = Command(
            "cli",
            params=[
                Option(["-f", "--format"], type=Choice(["json", "yaml", "xml"]))
            ],
        )

        completions = _get_words(cli, ["--format"], "")
        assert "json" in completions
        assert "yaml" in completions
        assert "xml" in completions

    def test_dynamic_completion(self):
        """Test that dynamic completion functions work."""
        def complete_fruits(ctx, param, incomplete):
            return [
                CompletionItem("apple", help="Red fruit"),
                CompletionItem("banana", help="Yellow fruit"),
                CompletionItem("cherry", help="Red small fruit"),
            ]

        cli = Command(
            "cli",
            params=[
                Argument(["fruit"], shell_complete=complete_fruits)
            ],
        )

        completions = _get_completions(cli, [], "")
        values = [c.value for c in completions]
        assert "apple" in values
        assert "banana" in values
        assert "cherry" in values

        helps = [c.help for c in completions]
        assert "Red fruit" in helps
        assert "Yellow fruit" in helps

    def test_dynamic_completion_with_filter(self):
        """Test that dynamic completion filters by incomplete value."""
        def complete_fruits(ctx, param, incomplete):
            fruits = ["apple", "apricot", "banana", "blueberry"]
            return [f for f in fruits if f.startswith(incomplete)]

        cli = Command(
            "cli",
            params=[
                Argument(["fruit"], shell_complete=complete_fruits)
            ],
        )

        completions = _get_words(cli, [], "a")
        assert "apple" in completions
        assert "apricot" in completions
        assert "banana" not in completions

        completions = _get_words(cli, [], "b")
        assert "banana" in completions
        assert "blueberry" in completions
        assert "apple" not in completions

    def test_nested_subcommands(self):
        """Test nested subcommand completion."""
        cli = Group(
            "cli",
            commands=[
                Group(
                    "user",
                    commands=[
                        Command("add"),
                        Command("delete"),
                        Command("list"),
                    ],
                ),
                Group(
                    "project",
                    commands=[
                        Command("create"),
                        Command("delete"),
                    ],
                ),
            ],
        )

        assert "user" in _get_words(cli, [], "")
        assert "project" in _get_words(cli, [], "")
        assert "add" in _get_words(cli, ["user"], "")
        assert "delete" in _get_words(cli, ["user"], "")
        assert "create" in _get_words(cli, ["project"], "")

    def test_path_completion_type(self):
        """Test that Path type provides proper completion type."""
        cli = Command(
            "cli",
            params=[
                Option(["-f", "--file"], type=Path()),
                Option(["-d", "--dir"], type=Path(file_okay=False)),
            ],
        )

        file_completions = _get_completions(cli, ["--file"], "/test")
        assert len(file_completions) == 1
        assert file_completions[0].type == "file"

        dir_completions = _get_completions(cli, ["--dir"], "/test")
        assert len(dir_completions) == 1
        assert dir_completions[0].type == "dir"
