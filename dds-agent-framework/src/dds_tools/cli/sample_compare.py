"""CLI for comparing DDS samples in JSONL format.

This tool compares captured DDS samples against expected output, with
configurable float tolerance for numerical comparisons.

Usage:
    dds-sample-compare --actual samples.jsonl --expected expected.jsonl
    dds-sample-compare --actual samples.jsonl --expected expected.jsonl --tolerance 1e-6
"""

import sys

import click

from dds_tools.core.sample_comparator import SampleComparator


@click.command()
@click.option(
    "--actual",
    "-a",
    type=click.Path(exists=True),
    required=True,
    help="Path to actual output JSONL file",
)
@click.option(
    "--expected",
    "-e",
    type=click.Path(exists=True),
    required=True,
    help="Path to expected output JSONL file",
)
@click.option(
    "--tolerance",
    "-t",
    type=float,
    default=1e-6,
    help="Float comparison tolerance (default: 1e-6)",
)
@click.option(
    "--ignore",
    "-i",
    multiple=True,
    help="Field paths to ignore (can be specified multiple times)",
)
@click.option(
    "--order-independent",
    is_flag=True,
    help="Compare samples regardless of order",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output result as JSON",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed mismatch information",
)
@click.option(
    "--max-mismatches",
    type=int,
    default=10,
    help="Maximum number of mismatches to show (default: 10)",
)
def main(
    actual: str,
    expected: str,
    tolerance: float,
    ignore: tuple[str, ...],
    order_independent: bool,
    as_json: bool,
    verbose: bool,
    max_mismatches: int,
) -> None:
    """Compare DDS samples captured in JSONL format.

    This tool compares actual output against expected output, with special
    handling for floating-point comparisons. It reports any mismatches
    with detailed field-level information.

    Examples:

        # Basic comparison
        dds-sample-compare --actual samples.jsonl --expected expected.jsonl

        # With tolerance for float comparison
        dds-sample-compare -a samples.jsonl -e expected.jsonl --tolerance 0.001

        # Ignore timestamp fields
        dds-sample-compare -a samples.jsonl -e expected.jsonl --ignore timestamp

        # Order-independent comparison
        dds-sample-compare -a samples.jsonl -e expected.jsonl --order-independent

    Exit codes:
        0 - All samples match
        1 - Samples do not match
        2 - Error (file not found, invalid JSON, etc.)
    """
    comparator = SampleComparator(
        float_tolerance=tolerance,
        ignore_fields=list(ignore),
        order_independent=order_independent,
    )

    result = comparator.compare_files(actual, expected)

    if as_json:
        click.echo(result.to_json())
    else:
        _print_result(result, verbose, max_mismatches)

    # Exit with appropriate code
    if result.error:
        sys.exit(2)
    elif result.passed:
        sys.exit(0)
    else:
        sys.exit(1)


def _print_result(result, verbose: bool, max_mismatches: int) -> None:
    """Print formatted comparison result."""
    # Print summary
    if result.passed:
        click.secho("✓ PASSED", fg="green", bold=True)
    else:
        click.secho("✗ FAILED", fg="red", bold=True)

    click.echo()
    click.echo(f"Actual samples:   {result.actual_count}")
    click.echo(f"Expected samples: {result.expected_count}")
    click.echo(f"Matched samples:  {result.matched_count}")

    if result.error:
        click.echo()
        click.secho(f"Error: {result.error}", fg="red")
        return

    if result.mismatches:
        click.echo()
        click.echo(f"Mismatches: {len(result.mismatches)}")

        # Show mismatches
        shown = 0
        for mismatch in result.mismatches:
            if shown >= max_mismatches:
                remaining = len(result.mismatches) - max_mismatches
                click.echo(f"  ... and {remaining} more")
                break

            click.echo()
            if mismatch.index >= 0:
                click.secho(f"  Sample {mismatch.index}:", fg="yellow")
            click.echo(f"    {mismatch.message}")

            if verbose and mismatch.field_mismatches:
                for fm in mismatch.field_mismatches[:5]:  # Limit field mismatches
                    click.echo(f"      - {fm.path}: {fm.message}")
                    click.echo(f"        actual:   {fm.actual}")
                    click.echo(f"        expected: {fm.expected}")

                if len(mismatch.field_mismatches) > 5:
                    remaining = len(mismatch.field_mismatches) - 5
                    click.echo(f"        ... and {remaining} more field mismatches")

            shown += 1


if __name__ == "__main__":
    main()

