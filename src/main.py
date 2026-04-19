#!/usr/bin/env python3
"""
BLG 480E Project 2 - Multi-Agent Web Crawler & Search System
Main CLI interface for the web crawler and search system.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Tuple

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

# Import using relative imports when run as module
from .crawler.web_crawler import WebCrawler
from .search.search_engine import SearchEngine
from .database.db_manager import DatabaseManager
from .utils.config import Config
from .utils.logger import setup_logging

console = Console()

@click.group()
@click.option('--config', '-c', default='config/settings.yaml', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """BLG 480E Project 2 - Multi-Agent Web Crawler & Search System"""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load configuration
    try:
        ctx.obj['config'] = Config.load(config)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Setup logging
    log_level = "DEBUG" if verbose else ctx.obj['config'].monitoring.log_level
    setup_logging(log_level)

@cli.command()
@click.option('--origin', '-o', required=True, help='Origin URL to start crawling')
@click.option('--depth', '-d', type=int, required=True, help='Maximum crawl depth')
@click.option('--rate-limit', '-r', type=int, help='Rate limit (requests per second)')
@click.option('--max-pages', '-m', type=int, help='Maximum pages to crawl')
@click.pass_context
def index(ctx, origin: str, depth: int, rate_limit: int, max_pages: int):
    """Start web crawling from origin URL to specified depth."""
    asyncio.run(_index_async(ctx.obj['config'], origin, depth, rate_limit, max_pages))

async def _index_async(config, origin: str, depth: int, rate_limit: int, max_pages: int):
    """Async implementation of the index command."""
    console.print(f"[green]Starting web crawl:[/green]")
    console.print(f"  Origin: {origin}")
    console.print(f"  Max Depth: {depth}")
    console.print(f"  Rate Limit: {rate_limit or 'default'}")
    console.print(f"  Max Pages: {max_pages or 'unlimited'}")

    search_engine = None
    try:
        # Initialize components
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        # Initialize search engine for real-time indexing
        search_engine = SearchEngine(config.search, db_manager)
        await search_engine.initialize()

        # Create crawler with search engine integration
        crawler = WebCrawler(config.crawler, db_manager, search_engine)

        # Start crawling with progress display
        with Progress() as progress:
            task = progress.add_task("Crawling...", total=max_pages or 1000)

            async for crawled_count in crawler.crawl(origin, depth, max_pages):
                progress.update(task, completed=crawled_count)

        console.print(f"[green]Crawling completed![/green] {crawler.pages_crawled} pages indexed.")

    except Exception as e:
        console.print(f"[red]Error during crawling: {e}[/red]")
        logging.error(f"Crawling error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up search engine
        if search_engine:
            await search_engine.shutdown()

@cli.command()
@click.option('--query', '-q', required=True, help='Search query')
@click.option('--limit', '-l', type=int, default=20, help='Maximum number of results')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'yaml']),
              default='table', help='Output format')
@click.pass_context
def search(ctx, query: str, limit: int, output_format: str):
    """Search indexed content for relevant URLs."""
    asyncio.run(_search_async(ctx.obj['config'], query, limit, output_format))

async def _search_async(config, query: str, limit: int, output_format: str):
    """Async implementation of the search command."""
    search_engine = None
    try:
        # Initialize components
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        search_engine = SearchEngine(config.search, db_manager)
        await search_engine.initialize()

        console.print(f"[green]Searching for:[/green] '{query}'")

        # Perform search
        results = await search_engine.search(query, limit)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        # Display results
        if output_format == 'table':
            _display_results_table(results)
        elif output_format == 'json':
            import json
            console.print(json.dumps([
                {"url": url, "origin": origin, "depth": depth, "score": score}
                for url, origin, depth, score in results
            ], indent=2))
        elif output_format == 'yaml':
            import yaml
            console.print(yaml.dump([
                {"url": url, "origin": origin, "depth": depth, "score": score}
                for url, origin, depth, score in results
            ], default_flow_style=False))

    except Exception as e:
        console.print(f"[red]Error during search: {e}[/red]")
        logging.error(f"Search error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up search engine
        if search_engine:
            await search_engine.shutdown()

@cli.command()
@click.pass_context
def status(ctx):
    """Display current system status and statistics."""
    asyncio.run(_status_async(ctx.obj['config']))

async def _status_async(config):
    """Async implementation of the status command."""
    try:
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        # Get system statistics
        stats = await db_manager.get_system_stats()

        # Create status table
        table = Table(title="System Status", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Pages Crawled", str(stats.get('total_pages', 0)))
        table.add_row("Unique Domains", str(stats.get('unique_domains', 0)))
        table.add_row("Index Size", f"{stats.get('index_size', 0)} terms")
        table.add_row("Database Size", f"{stats.get('db_size', 0)} MB")
        table.add_row("Last Crawl", stats.get('last_crawl', 'Never'))
        table.add_row("System Uptime", stats.get('uptime', 'Unknown'))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error getting system status: {e}[/red]")
        logging.error(f"Status error: {e}", exc_info=True)

@cli.command()
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
@click.pass_context
def stats(ctx, detailed: bool):
    """Display detailed system statistics and performance metrics."""
    asyncio.run(_stats_async(ctx.obj['config'], detailed))

async def _stats_async(config, detailed: bool):
    """Async implementation of the stats command."""
    try:
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()

        # Get detailed statistics
        if detailed:
            stats = await db_manager.get_detailed_stats()

            # Performance metrics table
            perf_table = Table(title="Performance Metrics", show_header=True)
            perf_table.add_column("Metric", style="cyan")
            perf_table.add_column("Value", style="green")

            for key, value in stats.get('performance', {}).items():
                perf_table.add_row(key.replace('_', ' ').title(), str(value))

            console.print(perf_table)

            # Queue status table
            if 'queue_status' in stats:
                queue_table = Table(title="Queue Status", show_header=True)
                queue_table.add_column("Queue", style="cyan")
                queue_table.add_column("Depth", style="yellow")
                queue_table.add_column("Pending", style="green")

                for queue_info in stats['queue_status']:
                    queue_table.add_row(
                        queue_info.get('name', ''),
                        str(queue_info.get('depth', '')),
                        str(queue_info.get('pending', ''))
                    )

                console.print(queue_table)
        else:
            # Call basic status display
            await _status_async(config)

    except Exception as e:
        console.print(f"[red]Error getting statistics: {e}[/red]")
        logging.error(f"Statistics error: {e}", exc_info=True)

def _display_results_table(results: List[Tuple[str, str, int, float]]):
    """Display search results in a formatted table."""
    table = Table(title="Search Results", show_header=True)
    table.add_column("URL", style="cyan", no_wrap=False)
    table.add_column("Origin", style="yellow")
    table.add_column("Depth", style="green")
    table.add_column("Relevance", style="magenta")

    for url, origin, depth, score in results:
        # Truncate long URLs for display
        display_url = url if len(url) <= 60 else url[:57] + "..."
        display_origin = origin if len(origin) <= 30 else origin[:27] + "..."

        table.add_row(
            display_url,
            display_origin,
            str(depth),
            f"{score:.3f}"
        )

    console.print(table)

def main():
    """Main entry point for the CLI application."""
    cli()

if __name__ == "__main__":
    main()