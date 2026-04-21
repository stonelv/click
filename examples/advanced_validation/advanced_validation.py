import click


def validate_even_number(ctx, param, value):
    if value % 2 != 0:
        raise click.ValidationError(f"{value} is not an even number")
    return value


@click.group()
def cli():
    """Advanced validation examples demonstrating Click's built-in
    parameter validation and constraint mechanisms.
    """
    pass


@cli.command()
@click.option("--age", type=int, min_val=0, max_val=120, help="Age must be between 0 and 120.")
@click.option("--score", type=float, min_val=0.0, max_val=100.0, min_open=True, max_open=True,
              help="Score must be between 0 and 100 (exclusive).")
def range_validation(age, score):
    """Validate numeric parameters using range constraints.
    
    Examples:
      advanced-validation range-validation --age 25 --score 50.5
      advanced-validation range-validation --age 150  # Error
    """
    click.echo(f"Age: {age}")
    click.echo(f"Score: {score}")


@cli.command()
@click.option("--email", regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
              help="Email address matching the pattern.")
@click.option("--zipcode", pattern=r"^\d{5}(-\d{4})?$",
              help="US zipcode (5 digits or 5+4 digits).")
@click.option("--username", pattern=r"^[a-z][a-z0-9_]{2,15}$",
              help="Lowercase username, 3-16 characters.")
def regex_validation(email, zipcode, username):
    """Validate string parameters using regex patterns.
    
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
@click.option("--price", type=float, min_val=0.01,
              validation_callback=lambda ctx, param, v: round(v, 2),
              help="Price (rounded to 2 decimals).")
def combined(number, price):
    """Combine multiple validation rules with callback.
    
    Examples:
      advanced-validation combined --number 42 --price 19.99
      advanced-validation combined --number 3  # Error (not even)
    """
    click.echo(f"Number: {number}")
    click.echo(f"Price: {price}")


@cli.command()
@click.argument("count", type=int, min_val=1, max_val=10)
@click.argument("code", pattern=r"^[A-Z]{3}$")
def args_validation(count, code):
    """Validate positional arguments.
    
    Examples:
      advanced-validation args-validation 5 ABC
      advanced-validation args-validation 15 ABC  # Error
      advanced-validation args-validation 5 abcd  # Error
    """
    click.echo(f"Count: {count}")
    click.echo(f"Code: {code}")


@cli.command()
@click.option("--tag", multiple=True, pattern=r"^[a-z][a-z0-9_]+$",
              help="Tags (lowercase, starts with letter).")
def multiple_values(tag):
    """Validate multiple values.
    
    Examples:
      advanced-validation multiple-values --tag python --tag cli
      advanced-validation multiple-values --tag InvalidTag  # Error
    """
    click.echo(f"Tags: {list(tag)}")


if __name__ == "__main__":
    cli()
