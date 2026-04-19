#!/usr/bin/env python3
"""
Database Reset Script for BLG 480E Project 2
Completely resets the database by removing all data and recreating tables.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.db_manager import DatabaseManager
from src.utils.config import Config
from src.utils.logger import setup_logging

async def reset_database(config_path: str = "config/settings.yaml"):
    """
    Reset the database by removing all data and recreating tables.

    Args:
        config_path: Path to configuration file
    """
    print("🔄 BLG 480E Project 2 - Database Reset")
    print("=" * 40)

    try:
        # Load configuration
        print(f"📁 Loading configuration from {config_path}")
        config = Config.load(config_path)

        # Setup logging
        setup_logging("INFO")
        logger = logging.getLogger(__name__)

        # Get database path
        db_path = config.database.database_url.replace("sqlite:///", "")
        db_file = Path(db_path)

        # Remove existing database file
        if db_file.exists():
            print(f"🗑️  Removing existing database: {db_path}")
            db_file.unlink()
            print("✅ Database file removed")
        else:
            print(f"ℹ️  Database file does not exist: {db_path}")

        # Recreate database
        print("🗄️  Recreating database with fresh schema...")
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        # Verify database was created successfully
        if Path(db_path).exists():
            print(f"✅ Database successfully recreated: {db_path}")

            # Get initial statistics
            stats = await db_manager.get_system_stats()
            print("\n📊 New Database Status:")
            print(f"   • Total pages: {stats['total_pages']}")
            print(f"   • Database size: {stats['db_size']} MB")
            print(f"   • Status: Fresh and ready")
        else:
            print(f"❌ Database recreation failed: {db_path}")
            return False

        # Clean up
        await db_manager.shutdown()

        print("\n🎉 Database reset completed successfully!")
        print("\n🚀 You can now start fresh:")
        print("   1. Start crawling: python -m src.main index --origin <URL> --depth <N>")
        print("   2. Search content: python -m src.main search --query '<QUERY>'")

        return True

    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        logging.error(f"Database reset error: {e}", exc_info=True)
        return False

def main():
    """Main entry point for the database reset script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Reset the BLG 480E Project 2 web crawler database"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/settings.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reset without confirmation prompt"
    )

    args = parser.parse_args()

    # Confirmation prompt unless force flag is used
    if not args.force:
        print("⚠️  WARNING: This will permanently delete all crawled data!")
        response = input("Are you sure you want to reset the database? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Database reset cancelled.")
            return

    # Run reset
    success = asyncio.run(reset_database(args.config))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()