"""CLI entry point for the real estate monitor."""

import sys
import os
import logging
import click

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.matcher import run_monitor
from app.state import reset_state, init_db, get_seen_count


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Emlak Monitor - Real estate listing tracker for Azerbaijan."""
    pass


@cli.command()
@click.option("--dry-run", is_flag=True, help="Run without sending notifications")
def run(dry_run: bool):
    """Run the monitor to check for new listings."""
    if dry_run:
        logger.info("Running in DRY-RUN mode (no notifications will be sent)")
    stats = run_monitor(dry_run=dry_run)
    if stats["errors"] > 0:
        logger.warning(f"Completed with {stats['errors']} errors")
    else:
        logger.info("Completed successfully")


@cli.command()
def status():
    """Show the current state of the monitor."""
    conn = init_db()
    count = get_seen_count(conn)
    conn.close()
    click.echo(f"Seen listings: {count}")


@cli.command(name="reset")
@click.confirmation_option(prompt="Are you sure you want to reset the state?")
def reset_cmd():
    """Reset the state database (mark all listings as unseen)."""
    reset_state()
    click.echo("State has been reset. Next run will seed existing listings.")


if __name__ == "__main__":
    cli()
