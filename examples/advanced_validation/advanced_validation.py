import click


def validate_even_number(ctx, param, value):
    if value % 2 != 0:
        raise click.BadParameter(f"{value} is not an even number")
    return value


@click.group()
def cli():
    """Advanced validation examples demonstrating Click's built-in
    parameter validation and constraint mechanisms.
    """
    pass


@cli.command()
@click.option("--age", type=click.Range(base_type=int, min=0, max=120), help="Age must be between 0 and 120.")
@click.option("--score", type=click.Range(base_type=float, min=0.0, max=100.0, min_open=True, max_open=True),
              help="Score must be between 0 and 100 (exclusive).")
@click.option("--count", type=int, min_val=1, max_val=10, help="Count (using old API for compatibility).")
def range_validation(age, score, count):
    """Validate numeric parameters using range constraints.

    This example demonstrates both the new Range type (recommended)
    and the old min_val/max_val API (for backward compatibility).

    Range type supports:
    - Any comparable type (int, float, str, etc.)
    - Open/closed bounds (min_open, max_open)

    Examples:
      advanced-validation range-validation --age 25 --score 50.5 --count 5
      advanced-validation range-validation --age 150  # Error
    """
    click.echo(f"Age: {age}")
    click.echo(f"Score: {score}")
    click.echo(f"Count: {count}")


@cli.command()
@click.option("--email", type=click.Pattern(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
              help="Email address matching the pattern.")
@click.option("--zipcode", regex=r"^\d{5}(-\d{4})?$",
              help="US zipcode (5 digits or 5+4 digits, using old API).")
@click.option("--username", pattern=r"^[a-z][a-z0-9_]{2,15}$",
              help="Lowercase username, 3-16 characters (pattern alias).")
def regex_validation(email, zipcode, username):
    """Validate string parameters using regex patterns.

    This example demonstrates the new Pattern type (recommended)
    and the old regex/pattern API (for backward compatibility).

    Important: Pattern uses fullmatch semantics (the entire string
    must match), not match semantics (only matches at the beginning).

    Examples:
      advanced-validation regex-validation --email user@example.com --zipcode 12345 --username john_doe
      advanced-validation regex-validation --email invalid  # Error
    """
    click.echo(f"Email: {email}")
    click.echo(f"Zipcode: {zipcode}")
    click.echo(f"Username: {username}")


@cli.command()
@click.option("--username", help="Username for login.")
@click.option("--password", help="Password for login.")
@click.option("--login", is_flag=True, requires=["username", "password"],
              help="Perform login (requires --username and --password).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.option("--quiet", "-q", is_flag=True, exclusive_with="verbose",
              help="Quiet output (cannot be used with --verbose).")
@click.option("--json", is_flag=True, help="Output as JSON.")
@click.option("--xml", is_flag=True, help="Output as XML.")
@click.option("--csv", is_flag=True, exclusive_with=["json", "xml"],
              help="Output as CSV (cannot be used with --json or --xml).")
def relationships(username, password, login, verbose, quiet, json, xml, csv):
    """Validate parameter relationships (requires, exclusive_with).

    These parameters define relationships between options:
    - requires: An option can only be used if another option is present
    - exclusive_with: An option cannot be used together with other options

    Examples:
      advanced-validation relationships --login --username admin --password secret
      advanced-validation relationships --verbose --quiet  # Error
      advanced-validation relationships --json --csv  # Error
    """
    if login:
        click.echo(f"Logging in as: {username}")
    
    if verbose:
        click.echo("Verbose mode enabled")
    elif quiet:
        click.echo("Quiet mode enabled")
    
    if json:
        click.echo("Output format: JSON")
    elif xml:
        click.echo("Output format: XML")
    elif csv:
        click.echo("Output format: CSV")


@cli.command()
@click.option("--number", type=int, min_val=1, max_val=100,
              validation_callback=validate_even_number,
              help="Even number between 1 and 100.")
@click.option("--price", type=click.Range(base_type=float, min=0.01),
              validation_callback=lambda ctx, param, v: round(v, 2),
              help="Price (rounded to 2 decimals, minimum 0.01).")
def combined(number, price):
    """Combine multiple validation rules with callback.

    You can combine:
    - Range validation (Range type or min_val/max_val)
    - Pattern validation (Pattern type or regex/pattern)
    - validation_callback for custom validation/transformation

    Important: Use click.BadParameter instead of click.ValidationError
    (which is deprecated and removed).

    Examples:
      advanced-validation combined --number 42 --price 19.99
      advanced-validation combined --number 3  # Error (not even)
    """
    click.echo(f"Number: {number}")
    click.echo(f"Price: {price}")


@cli.command()
@click.argument("count", type=click.Range(base_type=int, min=1, max=10))
@click.argument("code", type=click.Pattern(r"^[A-Z]{3}$"))
def args_validation(count, code):
    """Validate positional arguments.

    Arguments support the same validation as options:
    - Range type for numeric constraints
    - Pattern type for regex constraints
    - requires/exclusive_with for relationships

    Examples:
      advanced-validation args-validation 5 ABC
      advanced-validation args-validation 15 ABC  # Error
      advanced-validation args-validation 5 abcd  # Error
    """
    click.echo(f"Count: {count}")
    click.echo(f"Code: {code}")


@cli.command()
@click.option("--tag", multiple=True, type=click.Pattern(r"^[a-z][a-z0-9_]+$"),
              help="Tags (lowercase, starts with letter).")
def multiple_values(tag):
    """Validate multiple values.

    Both options with multiple=True and arguments with nargs
    support validation with Range and Pattern types.

    Examples:
      advanced-validation multiple-values --tag python --tag cli
      advanced-validation multiple-values --tag InvalidTag  # Error
    """
    click.echo(f"Tags: {list(tag)}")


@cli.command()
@click.option("--letter", type=click.Range(base_type=str, min="a", max="z"),
              help="A single lowercase letter (using string comparison).")
@click.option("--grade", type=click.Range(base_type=str, min="A", max="F", max_open=True),
              help="Grade from A to E (F is excluded using open bound).")
def custom_types(letter, grade):
    """Validate with non-numeric comparable types.

    Range type works with any comparable type, not just int/float.
    This includes:
    - Strings (lexicographic comparison)
    - Custom types that implement comparison operators

    Examples:
      advanced-validation custom-types --letter m --grade B
      advanced-validation custom-types --letter Z  # Error (uppercase)
      advanced-validation custom-types --grade F  # Error (excluded)
    """
    click.echo(f"Letter: {letter}")
    click.echo(f"Grade: {grade}")


if __name__ == "__main__":
    cli()
