#!/usr/bin/env python3
"""
Database Initialization Script for BLG 480E Project 2
Creates and initializes the SQLite database with proper schema.
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

async def init_database(config_path: str = "config/settings.yaml"):
    """
    Initialize the database with proper schema.

    Args:
        config_path: Path to configuration file
    """
    print("🔧 BLG 480E Project 2 - Database Initialization")
    print("=" * 50)

    try:
        # Load configuration
        print(f"📁 Loading configuration from {config_path}")
        config = Config.load(config_path)

        # Setup logging
        setup_logging("INFO")
        logger = logging.getLogger(__name__)

        # Create data directory if it doesn't exist
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        print(f"📂 Data directory: {data_dir.absolute()}")

        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        print(f"📝 Logs directory: {logs_dir.absolute()}")

        # Initialize database manager
        print("🗄️  Initializing database...")
        db_manager = DatabaseManager(config.database)

        # Initialize database (this will create tables)
        await db_manager.initialize()

        # Verify database was created successfully
        db_path = db_manager.db_path
        if Path(db_path).exists():
            print(f"✅ Database successfully created: {db_path}")

            # Get initial statistics
            stats = await db_manager.get_system_stats()
            print("\n📊 Database Status:")
            print(f"   • Total pages: {stats['total_pages']}")
            print(f"   • Database size: {stats['db_size']} MB")
            print(f"   • Last crawl: {stats['last_crawl']}")
        else:
            print(f"❌ Database creation failed: {db_path}")
            return False

        # Clean up
        await db_manager.shutdown()

        print("\n🎉 Database initialization completed successfully!")
        print("\n🚀 Next steps:")
        print("   1. Start crawling: python -m src.main index --origin <URL> --depth <N>")
        print("   2. Search content: python -m src.main search --query '<QUERY>'")
        print("   3. Check status: python -m src.main status")

        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database initialization error: {e}", exc_info=True)
        return False

def main():
    """Main entry point for the database initialization script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialize the BLG 480E Project 2 web crawler database"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/settings.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force initialization (recreate existing database)"
    )

    args = parser.parse_args()

    # Check if database already exists
    try:
        config = Config.load(args.config)
        db_path = Path(config.database.database_url.replace("sqlite:///", ""))

        if db_path.exists() and not args.force:
            print(f"⚠️  Database already exists: {db_path}")
            response = input("Do you want to continue? This will create/update tables. (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("Database initialization cancelled.")
                return

    except Exception as e:
        print(f"⚠️  Error checking existing database: {e}")

    # Run initialization
    success = asyncio.run(init_database(args.config))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()