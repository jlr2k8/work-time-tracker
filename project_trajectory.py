#!/usr/bin/env python3
"""
Project work hours trajectory to Nov 30 based on current data
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from track_work import get_commit_stats, estimate_hours_from_commits
from config import Config

def calculate_trajectory(repo_path: str, since_date: str = "2025-11-01", author: str = None):
    """
    Calculate current trajectory and project to Nov 30
    
    Args:
        repo_path: Path to git repository
        since_date: Start date for analysis (default: Nov 1, 2025)
        author: Optional author filter
    """
    today = datetime.now()
    nov_30 = datetime(2025, 11, 30)
    
    # Load config
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
                print(f"Trello integration enabled")
            except Exception as e:
                print(f"Warning: Trello integration failed: {e}")
    
    # Get stats from Nov 1 to today
    print(f"\n{'='*70}")
    print("CURRENT TRAJECTORY ANALYSIS")
    print(f"{'='*70}")
    print(f"Analyzing from {since_date} to {today.strftime('%Y-%m-%d')} (today)")
    print(f"Projecting to {nov_30.strftime('%Y-%m-%d')} (Nov 30)")
    
    # Warn if filters not set
    if not author:
        print("\nWARNING: No git author filter specified. This will include ALL commits.")
        print("   To filter to only your commits, provide your git author name.")
    if config.trello_member_id:
        print(f"Filtering Trello cards by your member ID")
    else:
        print("\nWARNING: TRELLO_MEMBER_ID not set. This will include cards assigned to others.")
        print("   Set TRELLO_MEMBER_ID in .env to filter to only your assigned cards.")
    print()
    
    stats = get_commit_stats(repo_path, since_date, author, trello_client, trello_board_id, config)
    
    if stats['commit_count'] == 0:
        print("No commits found in the period. Cannot calculate trajectory.")
        return
    
    # Calculate days worked
    commits = stats.get('commits', [])
    if not commits:
        print("No commits found.")
        return
    
    # Get unique dates with commits
    dates_with_work = set()
    for commit in commits:
        dates_with_work.add(commit['date'])
    
    # Calculate date range
    start_date = datetime.strptime(since_date, "%Y-%m-%d")
    days_elapsed = (today - start_date).days + 1  # +1 to include today
    days_with_work = len(dates_with_work)
    
    # Get billed hours (from Trello if available, otherwise commit-based)
    if stats.get('trello_enabled') and 'estimation_details' in stats:
        details = stats['estimation_details']
        matched_cards_with_hours = [m for m in details.get('matched_cards', []) if m.get('total_hours', 0) > 0]
        billed_hours = sum(m.get('total_hours', 0) for m in matched_cards_with_hours)
        total_work_hours = details.get('estimated_hours', 0)
    else:
        billed_hours = stats.get('estimated_hours', 0)
        total_work_hours = billed_hours
    
    # Calculate averages
    hours_per_day = billed_hours / days_elapsed if days_elapsed > 0 else 0
    hours_per_work_day = billed_hours / days_with_work if days_with_work > 0 else 0
    
    print(f"\nCURRENT PERIOD (Nov 1 - Today, Nov {today.day}):")
    print(f"  Days elapsed: {days_elapsed}")
    print(f"  Days with work: {days_with_work}")
    print(f"  Total hours: {billed_hours:.2f}h")
    print(f"  Average hours/day: {hours_per_day:.2f}h")
    print(f"  Average hours/work day: {hours_per_work_day:.2f}h")
    print(f"  Hourly rate: ${config.hourly_rate:.2f}")
    print(f"  Current amount: ${billed_hours * config.hourly_rate:,.2f}")
    
    # Project to Nov 30
    days_remaining = (nov_30 - today).days
    total_days_in_month = (nov_30 - start_date).days + 1
    
    # Projection scenarios
    print(f"\n{'='*70}")
    print("PROJECTIONS TO NOV 30:")
    print(f"{'='*70}")
    
    # Scenario 1: Continue at current daily average
    projected_hours_avg = billed_hours + (hours_per_day * days_remaining)
    projected_amount_avg = projected_hours_avg * config.hourly_rate
    
    print(f"\n1. CONTINUE AT CURRENT DAILY AVERAGE:")
    print(f"   Remaining days: {days_remaining}")
    print(f"   Projected additional hours: {hours_per_day * days_remaining:.2f}h")
    print(f"   Projected total hours: {projected_hours_avg:.2f}h")
    print(f"   Projected total amount: ${projected_amount_avg:,.2f}")
    
    # Scenario 2: Continue at current work-day average (only work on days you've been working)
    # Assume same work frequency
    work_days_remaining = int(days_remaining * (days_with_work / days_elapsed)) if days_elapsed > 0 else 0
    projected_hours_work_day = billed_hours + (hours_per_work_day * work_days_remaining)
    projected_amount_work_day = projected_hours_work_day * config.hourly_rate
    
    print(f"\n2. CONTINUE AT CURRENT WORK-DAY AVERAGE:")
    print(f"   Estimated work days remaining: {work_days_remaining}")
    print(f"   Projected additional hours: {hours_per_work_day * work_days_remaining:.2f}h")
    print(f"   Projected total hours: {projected_hours_work_day:.2f}h")
    print(f"   Projected total amount: ${projected_amount_work_day:,.2f}")
    
    # Scenario 3: Linear projection based on current rate
    if days_elapsed > 0:
        hours_per_day_rate = billed_hours / days_elapsed
        projected_hours_linear = hours_per_day_rate * total_days_in_month
        projected_amount_linear = projected_hours_linear * config.hourly_rate
        
        print(f"\n3. LINEAR PROJECTION (if current rate continues):")
        print(f"   Hours/day rate: {hours_per_day_rate:.2f}h")
        print(f"   Projected total hours: {projected_hours_linear:.2f}h")
        print(f"   Projected total amount: ${projected_amount_linear:,.2f}")
    
    # Show daily breakdown for context
    if commits:
        print(f"\n{'='*70}")
        print("DAILY BREAKDOWN (for context):")
        print(f"{'='*70}")
        commits_by_date = {}
        for commit in commits:
            date = commit['date']
            if date not in commits_by_date:
                commits_by_date[date] = []
            commits_by_date[date].append(commit)
        
        # Calculate hours per day
        daily_hours = {}
        for date, day_commits in commits_by_date.items():
            non_merge = [c for c in day_commits if 'merge' not in c.get('message', '').lower()]
            hours = estimate_hours_from_commits(non_merge)
            daily_hours[date] = hours
        
        # Show last 7 days
        sorted_dates = sorted(daily_hours.keys(), reverse=True)[:7]
        for date in sorted_dates:
            hours = daily_hours[date]
            print(f"  {date}: {hours:.2f}h")
    
    print(f"\n{'='*70}")
    print("RECOMMENDATION:")
    print(f"{'='*70}")
    print(f"Based on your current trajectory, you can reasonably expect:")
    print(f"  • Total hours by Nov 30: {projected_hours_avg:.1f}h - {projected_hours_work_day:.1f}h")
    print(f"  • Total amount by Nov 30: ${projected_amount_avg:,.2f} - ${projected_amount_work_day:,.2f}")
    print(f"\n(Assuming you maintain your current work pattern)")
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
    
    # Try to find repo if not provided
    if not repo_path:
        # Try common locations
        possible_paths = [
            "..",
            "../..",
            ".",
            Path.home() / "Desktop",
            Path.home() / "Documents",
        ]
        
        print("No repository path provided. Searching for git repositories...")
        for base_path in possible_paths:
            base = Path(base_path)
            if base.exists():
                # Look for .git directories
                for item in base.iterdir():
                    if item.is_dir() and (item / ".git").exists():
                        repo_path = str(item)
                        print(f"Found repository: {repo_path}")
                        break
                if repo_path:
                    break
        
        if not repo_path:
            print("\nCould not automatically find a git repository.")
            print("Usage: python project_trajectory.py <repo_path> [since_date] [author]")
            print("Example: python project_trajectory.py ../myproject 2025-11-01")
            sys.exit(1)
    
    # Validate repo path
    if not Path(repo_path).joinpath('.git').exists():
        print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
    
    calculate_trajectory(repo_path, since_date, author)
