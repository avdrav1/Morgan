#!/usr/bin/env python3
"""
Standalone migration runner script.

This script can be used to manually run migrations or check migration status.
It does not use locking, so it should only be used when you're certain
no other migration processes are running.

Usage:
    python scripts/run_migrations.py upgrade    # Run pending migrations
    python scripts/run_migrations.py current    # Show current version
    python scripts/run_migrations.py history    # Show migration history
    python scripts/run_migrations.py downgrade  # Downgrade one version
"""

import sys
import subprocess
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(asctime)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_alembic_command(command: list) -> bool:
    """
    Run an Alembic command.
    
    Args:
        command: List of command arguments (e.g., ['upgrade', 'head'])
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Running: alembic {' '.join(command)}")
        result = subprocess.run(
            ["alembic"] + command,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            logger.info("Command completed successfully")
            return True
        else:
            logger.error(f"Command failed with exit code {result.returncode}")
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
            
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python run_migrations.py <command>")
        print("\nCommands:")
        print("  upgrade     - Run pending migrations")
        print("  current     - Show current migration version")
        print("  history     - Show migration history")
        print("  downgrade   - Downgrade one version")
        print("  heads       - Show current available heads")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    if command == "upgrade":
        success = run_alembic_command(["upgrade", "head"])
    elif command == "current":
        success = run_alembic_command(["current"])
    elif command == "history":
        success = run_alembic_command(["history"])
    elif command == "downgrade":
        success = run_alembic_command(["downgrade", "-1"])
    elif command == "heads":
        success = run_alembic_command(["heads"])
    else:
        logger.error(f"Unknown command: {command}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
