import re
from datetime import date

import pytest

import click
from click.testing import CliRunner


class TestCompatibilityLayer:
    """Test backward compatibility with old validation parameters."""

    def test_min_val_compatibility(self, runner):
        """Test that min_val parameter still works."""

        @click.command()
        @click.option("--count", type=int, min_val=5)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "10"])
        assert result.exit_code == 0
        assert "count=10" in result.output

        result = runner.invoke(cli, ["--count", "3"])
        assert result.exit_code != 0
        assert "3 is not in the range x>=5" in result.output

    def test_max_val_compatibility(self, runner):
        """Test that max_val parameter still works."""

        @click.command()
        @click.option("--count", type=int, max_val=10)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "15"])
        assert result.exit_code != 0
        assert "15 is not in the range x<=10" in result.output

    def test_min_max_val_compatibility(self, runner):
        """Test that min_val and max_val together work."""

        @click.command()
        @click.option("--count", type=int, min_val=1, max_val=10)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "0"])
        assert result.exit_code != 0
        assert "0 is not in the range 1<=x<=10" in result.output

        result = runner.invoke(cli, ["--count", "11"])
        assert result.exit_code != 0
        assert "11 is not in the range 1<=x<=10" in result.output

    def test_open_bounds_compatibility(self, runner):
        """Test that min_open and max_open parameters work."""

        @click.command()
        @click.option("--count", type=int, min_val=1, max_val=10, min_open=True, max_open=True)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "1"])
        assert result.exit_code != 0
        assert "1 is not in the range 1<x<10" in result.output

        result = runner.invoke(cli, ["--count", "10"])
        assert result.exit_code != 0
        assert "10 is not in the range 1<x<10" in result.output

    def test_float_range_compatibility(self, runner):
        """Test that range validation works with floats."""

        @click.command()
        @click.option("--value", type=float, min_val=0.5, max_val=5.5)
        def cli(value):
            click.echo(f"value={value}")

        result = runner.invoke(cli, ["--value", "3.0"])
        assert result.exit_code == 0
        assert "value=3.0" in result.output

        result = runner.invoke(cli, ["--value", "0.1"])
        assert result.exit_code != 0
        assert "0.1 is not in the range 0.5<=x<=5.5" in result.output

    def test_regex_compatibility(self, runner):
        """Test that regex parameter still works."""

        @click.command()
        @click.option("--email", regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        def cli(email):
            click.echo(f"email={email}")

        result = runner.invoke(cli, ["--email", "test@example.com"])
        assert result.exit_code == 0
        assert "email=test@example.com" in result.output

        result = runner.invoke(cli, ["--email", "invalid-email"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_pattern_compatibility(self, runner):
        """Test that pattern parameter (alias for regex) still works."""

        @click.command()
        @click.option("--code", pattern=r"^[A-Z]{3}\d{3}$")
        def cli(code):
            click.echo(f"code={code}")

        result = runner.invoke(cli, ["--code", "ABC123"])
        assert result.exit_code == 0
        assert "code=ABC123" in result.output

        result = runner.invoke(cli, ["--code", "invalid"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_regex_with_compiled_pattern(self, runner):
        """Test that regex works with compiled pattern."""
        pattern = re.compile(r"^\d{4}$")

        @click.command()
        @click.option("--year", regex=pattern)
        def cli(year):
            click.echo(f"year={year}")

        result = runner.invoke(cli, ["--year", "2024"])
        assert result.exit_code == 0
        assert "year=2024" in result.output

        result = runner.invoke(cli, ["--year", "abc"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_validation_callback_compatibility(self, runner):
        """Test that validation_callback still works."""

        def validate_positive_even(ctx, param, value):
            if value <= 0 or value % 2 != 0:
                raise click.BadParameter("Must be a positive even number")
            return value

        @click.command()
        @click.option("--count", type=int, validation_callback=validate_positive_even)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "4"])
        assert result.exit_code == 0
        assert "count=4" in result.output

        result = runner.invoke(cli, ["--count", "3"])
        assert result.exit_code != 0
        assert "Must be a positive even number" in result.output

    def test_validation_callback_with_callback(self, runner):
        """Test that validation_callback works with existing callback."""

        def validate_even(ctx, param, value):
            if value % 2 != 0:
                raise click.BadParameter("Must be even")
            return value

        def double_value(ctx, param, value):
            return value * 2

        @click.command()
        @click.option("--value", type=int, validation_callback=validate_even, callback=double_value)
        def cli(value):
            click.echo(f"value={value}")

        result = runner.invoke(cli, ["--value", "4"])
        assert result.exit_code == 0
        assert "value=8" in result.output

        result = runner.invoke(cli, ["--value", "3"])
        assert result.exit_code != 0
        assert "Must be even" in result.output

    def test_multiple_validation_rules_compatibility(self, runner):
        """Test that multiple validation rules work together."""

        @click.command()
        @click.option(
            "--age",
            type=int,
            min_val=18,
            max_val=65,
            validation_callback=lambda ctx, param, value: value * 2,
        )
        def cli(age):
            click.echo(f"age={age}")

        result = runner.invoke(cli, ["--age", "25"])
        assert result.exit_code == 0
        assert "age=50" in result.output

        result = runner.invoke(cli, ["--age", "15"])
        assert result.exit_code != 0
        assert "15 is not in the range 18<=x<=65" in result.output


class TestRangeType:
    """Test the new Range type for generic range validation."""

    def test_range_with_int(self, runner):
        """Test Range with int base type."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, min=1, max=10))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "0"])
        assert result.exit_code != 0
        assert "0 is not in the range 1<=x<=10" in result.output

        result = runner.invoke(cli, ["--count", "11"])
        assert result.exit_code != 0
        assert "11 is not in the range 1<=x<=10" in result.output

    def test_range_with_float(self, runner):
        """Test Range with float base type."""

        @click.command()
        @click.option("--value", type=click.Range(base_type=float, min=0.5, max=5.5))
        def cli(value):
            click.echo(f"value={value}")

        result = runner.invoke(cli, ["--value", "3.0"])
        assert result.exit_code == 0
        assert "value=5.0" not in result.output

        result = runner.invoke(cli, ["--value", "0.1"])
        assert result.exit_code != 0
        assert "0.1 is not in the range 0.5<=x<=5.5" in result.output

    def test_range_with_open_bounds(self, runner):
        """Test Range with open bounds (min_open, max_open)."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, min=1, max=10, min_open=True, max_open=True))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "1"])
        assert result.exit_code != 0
        assert "1 is not in the range 1<x<10" in result.output

        result = runner.invoke(cli, ["--count", "10"])
        assert result.exit_code != 0
        assert "10 is not in the range 1<x<10" in result.output

    def test_range_with_min_only(self, runner):
        """Test Range with only min bound."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, min=5))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "10"])
        assert result.exit_code == 0
        assert "count=10" in result.output

        result = runner.invoke(cli, ["--count", "3"])
        assert result.exit_code != 0
        assert "3 is not in the range x>=5" in result.output

    def test_range_with_max_only(self, runner):
        """Test Range with only max bound."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, max=10))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "15"])
        assert result.exit_code != 0
        assert "15 is not in the range x<=10" in result.output

    def test_range_with_comparable_types(self, runner):
        """Test Range with non-numeric comparable types (e.g., strings)."""

        @click.command()
        @click.option("--letter", type=click.Range(base_type=str, min="a", max="z"))
        def cli(letter):
            click.echo(f"letter={letter}")

        result = runner.invoke(cli, ["--letter", "m"])
        assert result.exit_code == 0
        assert "letter=m" in result.output

        result = runner.invoke(cli, ["--letter", "A"])
        assert result.exit_code != 0


class TestPatternType:
    """Test the new Pattern type for regex validation."""

    def test_pattern_basic(self, runner):
        """Test basic pattern matching."""

        @click.command()
        @click.option("--code", type=click.Pattern(r"^[A-Z]{3}\d{3}$"))
        def cli(code):
            click.echo(f"code={code}")

        result = runner.invoke(cli, ["--code", "ABC123"])
        assert result.exit_code == 0
        assert "code=ABC123" in result.output

        result = runner.invoke(cli, ["--code", "invalid"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_pattern_fullmatch_semantics(self, runner):
        """Test that Pattern uses fullmatch (not match) semantics."""

        @click.command()
        @click.option("--code", type=click.Pattern(r"\d{3}"))
        def cli(code):
            click.echo(f"code={code}")

        result = runner.invoke(cli, ["--code", "123"])
        assert result.exit_code == 0
        assert "code=123" in result.output

        result = runner.invoke(cli, ["--code", "1234"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

        result = runner.invoke(cli, ["--code", "abc123"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_pattern_with_compiled_regex(self, runner):
        """Test Pattern with compiled regex."""
        compiled = re.compile(r"^\d{4}$")

        @click.command()
        @click.option("--year", type=click.Pattern(compiled))
        def cli(year):
            click.echo(f"year={year}")

        result = runner.invoke(cli, ["--year", "2024"])
        assert result.exit_code == 0
        assert "year=2024" in result.output

        result = runner.invoke(cli, ["--year", "abc"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output

    def test_pattern_with_flags(self, runner):
        """Test Pattern with regex flags."""

        @click.command()
        @click.option("--name", type=click.Pattern(r"^[a-z]+$", flags=re.IGNORECASE))
        def cli(name):
            click.echo(f"name={name}")

        result = runner.invoke(cli, ["--name", "john"])
        assert result.exit_code == 0
        assert "name=john" in result.output

        result = runner.invoke(cli, ["--name", "JOHN"])
        assert result.exit_code == 0
        assert "name=JOHN" in result.output


class TestParameterRelationships:
    """Test parameter relationships (requires, exclusive_with)."""

    def test_requires_single(self, runner):
        """Test requires with single parameter."""

        @click.command()
        @click.option("--input", required=False)
        @click.option("--output", requires="input")
        def cli(input, output):
            click.echo(f"input={input}, output={output}")

        result = runner.invoke(cli, ["--input", "file.txt", "--output", "out.txt"])
        assert result.exit_code == 0
        assert "input=file.txt, output=out.txt" in result.output

        result = runner.invoke(cli, ["--output", "out.txt"])
        assert result.exit_code != 0
        assert "requires" in result.output.lower()

    def test_requires_multiple(self, runner):
        """Test requires with multiple parameters."""

        @click.command()
        @click.option("--username")
        @click.option("--password")
        @click.option("--login", requires=["username", "password"])
        def cli(username, password, login):
            click.echo(f"login={login}")

        result = runner.invoke(
            cli, ["--username", "user", "--password", "pass", "--login", "yes"]
        )
        assert result.exit_code == 0
        assert "login=yes" in result.output

        result = runner.invoke(cli, ["--login", "yes"])
        assert result.exit_code != 0
        assert "requires" in result.output.lower()

    def test_exclusive_with_single(self, runner):
        """Test exclusive_with with single parameter."""

        @click.command()
        @click.option("--verbose", is_flag=True)
        @click.option("--quiet", is_flag=True, exclusive_with="verbose")
        def cli(verbose, quiet):
            click.echo(f"verbose={verbose}, quiet={quiet}")

        result = runner.invoke(cli, ["--verbose"])
        assert result.exit_code == 0
        assert "verbose=True, quiet=False" in result.output

        result = runner.invoke(cli, ["--quiet"])
        assert result.exit_code == 0
        assert "verbose=False, quiet=True" in result.output

        result = runner.invoke(cli, ["--verbose", "--quiet"])
        assert result.exit_code != 0
        assert "cannot be used with" in result.output

    def test_exclusive_with_multiple(self, runner):
        """Test exclusive_with with multiple parameters."""

        @click.command()
        @click.option("--json", is_flag=True)
        @click.option("--xml", is_flag=True)
        @click.option("--csv", is_flag=True, exclusive_with=["json", "xml"])
        def cli(json, xml, csv):
            click.echo(f"json={json}, xml={xml}, csv={csv}")

        result = runner.invoke(cli, ["--csv"])
        assert result.exit_code == 0
        assert "json=False, xml=False, csv=True" in result.output

        result = runner.invoke(cli, ["--json", "--csv"])
        assert result.exit_code != 0
        assert "cannot be used with" in result.output


class TestHelpDisplay:
    """Test that validation rules are shown in help."""

    def test_range_in_help(self, runner):
        """Test that range validation is shown in help."""

        @click.command()
        @click.option("--count", type=int, min_val=1, max_val=10)
        def cli(count):
            pass

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "1<=x<=10" in result.output

    def test_range_type_in_help(self, runner):
        """Test that Range type is shown in help."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, min=1, max=10))
        def cli(count):
            pass

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "1<=x<=10" in result.output

    def test_pattern_in_help(self, runner):
        """Test that pattern is shown in help."""

        @click.command()
        @click.option("--email", regex=r"^[a-z]+@[a-z]+\.[a-z]+$")
        def cli(email):
            pass

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "pattern:" in result.output

    def test_pattern_type_in_help(self, runner):
        """Test that Pattern type is shown in help."""

        @click.command()
        @click.option("--email", type=click.Pattern(r"^[a-z]+@[a-z]+\.[a-z]+$"))
        def cli(email):
            pass

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "pattern:" in result.output


class TestArgumentValidation:
    """Test that validation works with arguments."""

    def test_argument_range_validation(self, runner):
        """Test that range validation works with arguments."""

        @click.command()
        @click.argument("count", type=int, min_val=1, max_val=10)
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["15"])
        assert result.exit_code != 0
        assert "15 is not in the range 1<=x<=10" in result.output

    def test_argument_regex_validation(self, runner):
        """Test that regex validation works with arguments."""

        @click.command()
        @click.argument("code", regex=r"^[A-Z]{3}$")
        def cli(code):
            click.echo(f"code={code}")

        result = runner.invoke(cli, ["ABC"])
        assert result.exit_code == 0
        assert "code=ABC" in result.output

        result = runner.invoke(cli, ["abcd"])
        assert result.exit_code != 0
        assert "does not match the pattern" in result.output


class TestMultipleValues:
    """Test validation with multiple values."""

    def test_multiple_range_validation(self, runner):
        """Test that range validation works with multiple=True."""

        @click.command()
        @click.option("--value", type=int, multiple=True, min_val=0, max_val=100)
        def cli(value):
            for v in value:
                click.echo(f"value={v}")

        result = runner.invoke(cli, ["--value", "10", "--value", "50"])
        assert result.exit_code == 0
        assert "value=10" in result.output
        assert "value=50" in result.output

        result = runner.invoke(cli, ["--value", "10", "--value", "200"])
        assert result.exit_code != 0
        assert "200 is not in the range" in result.output

    def test_multiple_with_range_type(self, runner):
        """Test multiple values with Range type."""

        @click.command()
        @click.option("--value", type=click.Range(base_type=int, min=0, max=100), multiple=True)
        def cli(value):
            for v in value:
                click.echo(f"value={v}")

        result = runner.invoke(cli, ["--value", "10", "--value", "50"])
        assert result.exit_code == 0
        assert "value=10" in result.output
        assert "value=50" in result.output


class TestErrorMessages:
    """Test that error messages are clear and consistent."""

    def test_range_error_message(self, runner):
        """Test range error message format."""

        @click.command()
        @click.option("--count", type=click.Range(base_type=int, min=1, max=10))
        def cli(count):
            pass

        result = runner.invoke(cli, ["--count", "0"])
        assert result.exit_code != 0
        assert "0 is not in the range 1<=x<=10" in result.output

    def test_pattern_error_message(self, runner):
        """Test pattern error message format."""

        @click.command()
        @click.option("--code", type=click.Pattern(r"\d{3}"))
        def cli(code):
            pass

        result = runner.invoke(cli, ["--code", "abc"])
        assert result.exit_code != 0
        assert "'abc' does not match the pattern" in result.output

    def test_requires_error_message(self, runner):
        """Test requires error message format."""

        @click.command()
        @click.option("--input")
        @click.option("--output", requires="input")
        def cli(input, output):
            pass

        result = runner.invoke(cli, ["--output", "out.txt"])
        assert result.exit_code != 0
        assert "requires" in result.output.lower()
        assert "input" in result.output.lower()

    def test_exclusive_with_error_message(self, runner):
        """Test exclusive_with error message format."""

        @click.command()
        @click.option("--verbose", is_flag=True)
        @click.option("--quiet", is_flag=True, exclusive_with="verbose")
        def cli(verbose, quiet):
            pass

        result = runner.invoke(cli, ["--verbose", "--quiet"])
        assert result.exit_code != 0
        assert "cannot be used with" in result.output
        assert "verbose" in result.output.lower()


class TestExistingIntRangeFloatRange:
    """Test that existing IntRange and FloatRange still work correctly."""

    def test_int_range_basic(self, runner):
        """Test IntRange basic functionality."""

        @click.command()
        @click.option("--count", type=click.IntRange(min=1, max=10))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "0"])
        assert result.exit_code != 0
        assert "0 is not in the range" in result.output

    def test_int_range_open_bounds(self, runner):
        """Test IntRange with open bounds."""

        @click.command()
        @click.option("--count", type=click.IntRange(min=1, max=10, min_open=True, max_open=True))
        def cli(count):
            click.echo(f"count={count}")

        result = runner.invoke(cli, ["--count", "5"])
        assert result.exit_code == 0
        assert "count=5" in result.output

        result = runner.invoke(cli, ["--count", "1"])
        assert result.exit_code != 0
        assert "1 is not in the range 1<x<10" in result.output

    def test_float_range_basic(self, runner):
        """Test FloatRange basic functionality."""

        @click.command()
        @click.option("--value", type=click.FloatRange(min=0.5, max=5.5))
        def cli(value):
            click.echo(f"value={value}")

        result = runner.invoke(cli, ["--value", "3.0"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["--value", "0.1"])
        assert result.exit_code != 0
        assert "0.1 is not in the range" in result.output
