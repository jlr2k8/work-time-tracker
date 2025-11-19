#!/usr/bin/env python3
"""
Simple projection: Use invoiced hours so far to project to Nov 30
"""

import sys
from datetime import datetime
from pathlib import Path
from track_work import get_commit_stats
from config import Config

def simple_projection(repo_path: str, since_date: str = "2025-11-01", author: str = None):
    """
    Simple projection based on invoiced hours so far
    """
    today = datetime.now()
    nov_30 = datetime(2025, 11, 30)
    
    config = Config()
    
    # Initialize Trello if available
    trello_client = None
    trello_board_id = None
    if config.has_trello_credentials():
        trello_board_id = config.trello_board_id
        if trello_board_id:
            try:
                from trello_client import TrelloClient
                trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
            except Exception as e:
                print(f"Warning: Trello integration failed: {e}")
    
    print(f"\n{'='*70}")
    print("SIMPLE PROJECTION TO NOV 30")
    print(f"{'='*70}")
    print(f"Period: {since_date} to {today.strftime('%Y-%m-%d')} (today)")
    print(f"Projecting to: {nov_30.strftime('%Y-%m-%d')} (Nov 30)")
    print()
    
    # Get current stats (what you've invoiced so far)
    stats = get_commit_stats(repo_path, since_date, author, trello_client, trello_board_id, config)
    
    if stats['commit_count'] == 0:
        print("No work found in this period.")
        return
    
    # Get billed hours - use commit-based hours (what you've actually worked)
    # This is simpler and more accurate for projection
    billed_hours = stats.get('estimated_hours', 0)
    
    # If Trello is enabled and we have matched cards, prefer that (but don't require member filter)
    if stats.get('trello_enabled') and 'estimation_details' in stats:
        details = stats['estimation_details']
        matched_cards_with_hours = [m for m in details.get('matched_cards', []) if m.get('total_hours', 0) > 0]
        trello_hours = sum(m.get('total_hours', 0) for m in matched_cards_with_hours)
        # Use Trello hours if available and reasonable, otherwise fall back to commit hours
        if trello_hours > 0:
            billed_hours = trello_hours
    
    billed_amount = billed_hours * config.hourly_rate
    
    # Calculate days
    start_date = datetime.strptime(since_date, "%Y-%m-%d")
    days_elapsed = (today - start_date).days + 1
    days_remaining = (nov_30 - today).days
    total_days_in_month = (nov_30 - start_date).days + 1
    
    # Calculate rate
    hours_per_day = billed_hours / days_elapsed if days_elapsed > 0 else 0
    
    # Project to Nov 30
    projected_hours = hours_per_day * total_days_in_month
    projected_amount = projected_hours * config.hourly_rate
    
    print(f"CURRENT (Nov 1 - Today):")
    print(f"  Days elapsed: {days_elapsed}")
    print(f"  Hours invoiced: {billed_hours:.2f}h")
    print(f"  Amount invoiced: ${billed_amount:,.2f}")
    print(f"  Rate: {hours_per_day:.2f} hours/day")
    print()
    print(f"PROJECTION TO NOV 30:")
    print(f"  Days remaining: {days_remaining}")
    print(f"  Projected total hours: {projected_hours:.2f}h")
    print(f"  Projected total amount: ${projected_amount:,.2f}")
    print()
    print(f"{'='*70}")
    print(f"ESTIMATE: ${projected_amount:,.2f} by Nov 30")
    print(f"{'='*70}")
    print()

if __name__ == "__main__":
    repo_path = None
    since_date = "2025-11-01"
    author = None
    
    if len(sys.argv) >= 2:
        repo_path = sys.argv[1]
    if len(sys.argv) >= 3:
        since_date = sys.argv[2]
    if len(sys.argv) >= 4:
        author = sys.argv[3]
    
    if not repo_path:
        print("Usage: python simple_projection.py <repo_path> [since_date] [author]")
        print("Example: python simple_projection.py ../ACME 2025-11-01")
        sys.exit(1)
    
    if not Path(repo_path).joinpath('.git').exists():
        print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
    
    simple_projection(repo_path, since_date, author)

