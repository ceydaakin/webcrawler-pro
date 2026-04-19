#!/usr/bin/env python3
"""
Search Index Rebuild Script for BLG 480E Project 2
Rebuilds the search index from existing crawled content.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine
from src.utils.config import Config
from src.utils.logger import setup_logging

async def rebuild_search_index(config_path: str = "config/settings.yaml"):
    """
    Rebuild the search index from existing crawled content.

    Args:
        config_path: Path to configuration file
    """
    print("🔄 BLG 480E Project 2 - Search Index Rebuild")
    print("=" * 45)

    try:
        # Load configuration
        print(f"📁 Loading configuration from {config_path}")
        config = Config.load(config_path)

        # Setup logging
        setup_logging("INFO")
        logger = logging.getLogger(__name__)

        # Initialize database manager
        print("🗄️  Connecting to database...")
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        # Check if there's any content to index
        stats = await db_manager.get_system_stats()
        total_pages = stats['total_pages']

        if total_pages == 0:
            print("ℹ️  No crawled content found. Nothing to index.")
            await db_manager.shutdown()
            return True

        print(f"📊 Found {total_pages} pages to reindex")

        # Initialize search engine
        print("🔍 Initializing search engine...")
        search_engine = SearchEngine(config.search, db_manager)
        await search_engine.initialize()

        # Clear existing search index
        print("🗑️  Clearing existing search index...")
        await search_engine._clear_search_index()

        # Rebuild index from all crawled pages
        print("⚙️  Rebuilding search index...")
        rebuilt_count = await search_engine._rebuild_index_from_database()

        print(f"✅ Search index rebuilt successfully!")
        print(f"📊 Indexed {rebuilt_count} pages")

        # Verify the rebuilt index
        print("🔍 Verifying search functionality...")
        test_results = await search_engine.search("test", limit=5)
        print(f"   • Test search returned {len(test_results)} results")

        # Clean up
        await search_engine.shutdown()
        await db_manager.shutdown()

        print("\n🎉 Index rebuild completed successfully!")
        print("\n🚀 You can now:")
        print("   1. Search content: python -m src.main search --query '<QUERY>'")
        print("   2. Check status: python -m src.main status")

        return True

    except Exception as e:
        print(f"❌ Index rebuild failed: {e}")
        logging.error(f"Index rebuild error: {e}", exc_info=True)
        return False

def main():
    """Main entry point for the index rebuild script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Rebuild the search index for BLG 480E Project 2"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/settings.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force rebuild without confirmation prompt"
    )

    args = parser.parse_args()

    # Confirmation prompt unless force flag is used
    if not args.force:
        print("ℹ️  This will rebuild the search index from existing crawled content.")
        response = input("Do you want to continue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Index rebuild cancelled.")
            return

    # Run rebuild
    success = asyncio.run(rebuild_search_index(args.config))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()