#!/usr/bin/env python3
"""
Debug script to see what commits are being counted for card 49
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.track_work import get_commit_stats, extract_task_number
from src.config import Config
from src.trello_client import TrelloClient

def debug_card_49(repo_path: str, since_date: str, trello_board_id: str, author: str = None):
    """Debug what commits are matched to card 49"""
    
    config = Config()
    trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
    
    # Get commit stats
    if not trello_board_id:
        print("ERROR: Trello board ID required")
        print("Set TRELLO_BOARD_ID environment variable or use --trello-board-id")
        return
    
    print(f"Debugging card 49 with:")
    print(f"  Repo path: {repo_path}")
    print(f"  Since date: {since_date}")
    print(f"  Trello board ID: {trello_board_id[:8]}...")
    if author:
        print(f"  Author filter: {author}")
    print()
    
    try:
        stats = get_commit_stats(
            repo_path=repo_path,
            since_date=since_date,
            author=author,
            trello_client=trello_client,
            trello_board_id=trello_board_id,
            config=config
        )
    except Exception as e:
        print(f"ERROR: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not stats.get('trello_enabled'):
        print("ERROR: Trello not enabled")
        print(f"  trello_board_id: {trello_board_id}")
        print(f"  has_trello_client: {trello_client is not None}")
        print(f"  commit_count: {stats.get('commit_count', 0)}")
        print(f"  Check if the repo path is correct and contains a .git directory")
        # Even if Trello not enabled, try to show what we can
        if stats.get('commit_count', 0) == 0:
            print("\n  No commits found - this might be why Trello is disabled")
            print("  Try a different date range or repo path")
        return
    
    details = stats.get('estimation_details', {})
    matched_cards = details.get('matched_cards', [])
    
    # Find card 49
    card_49 = None
    for match in matched_cards:
        card = match['card']
        task_num = extract_task_number(card)
        if task_num == '49':
            card_49 = match
            break
    
    if not card_49:
        print("Card 49 not found in matched cards")
        return
    
    card = card_49['card']
    commits = card_49.get('commits', [])
    comment_hours = card_49.get('comment_hours', 0)
    commit_hours = card_49.get('commit_based_hours', 0)
    total_hours = card_49.get('total_hours', 0)
    
    print(f"\n{'='*80}")
    print(f"Card #49: {card.get('name', 'Unknown')}")
    print(f"{'='*80}")
    print(f"Comment hours: {comment_hours:.2f}h")
    print(f"Commit hours: {commit_hours:.2f}h")
    print(f"Total hours: {total_hours:.2f}h")
    print(f"Calculation: ({comment_hours:.2f}h × 0.9) + ({commit_hours:.2f}h × 0.1) = {total_hours:.2f}h")
    print(f"\nMatched {len(commits)} commits:")
    print(f"{'='*80}")
    
    # Check for merge PRs
    merge_prs = []
    regular_commits = []
    
    for commit in commits:
        msg = commit.get('message', '').lower()
        is_merge_pr = ('merge pull request' in msg or 
                      'merge pr' in msg or
                      msg.startswith('merge pull request') or
                      msg.startswith('merge pr') or
                      ('merge' in msg and 'pull' in msg) or
                      ('merge' in msg and 'pr #' in msg))
        
        if is_merge_pr:
            merge_prs.append(commit)
        else:
            regular_commits.append(commit)
    
    if merge_prs:
        print(f"\nWARNING: Found {len(merge_prs)} merge PR commits (should be filtered out!):")
        for i, commit in enumerate(merge_prs, 1):
            msg = commit.get('message', '')
            lines = commit.get('lines_changed', 0)
            date = commit.get('date', '')
            print(f"  {i}. [{date}] {msg[:70]} ({lines} lines)")
    
    print(f"\nRegular commits ({len(regular_commits)}):")
    print(f"{'-'*80}")
    
    # Group by date
    from collections import defaultdict
    commits_by_date = defaultdict(list)
    for commit in regular_commits:
        date = commit.get('date', 'Unknown')
        commits_by_date[date].append(commit)
    
    total_lines = 0
    for date in sorted(commits_by_date.keys()):
        day_commits = commits_by_date[date]
        day_lines = sum(c.get('lines_changed', 0) for c in day_commits)
        total_lines += day_lines
        print(f"\n{date} ({len(day_commits)} commits, {day_lines:,} lines):")
        for commit in day_commits[:10]:  # Show first 10 per day
            msg = commit.get('message', '')
            lines = commit.get('lines_changed', 0)
            match_type = commit.get('_match_type', 'unknown')
            branches = commit.get('branches', [])
            branch_info = f" [branches: {', '.join(branches[:2])}]" if branches else ""
            print(f"  [{match_type}]{branch_info} {msg[:55]} ({lines:,} lines)")
        if len(day_commits) > 10:
            print(f"  ... and {len(day_commits) - 10} more commits")
    
    print(f"\n{'-'*80}")
    print(f"Total: {len(regular_commits)} commits, {total_lines:,} lines")
    print(f"Estimated hours from commits: {commit_hours:.2f}h")
    
    # Calculate what the hours should be
    if total_lines > 0:
        # Use same logic as estimate_hours_from_commits
        lines_per_hour = 250  # Default
        estimated = total_lines / lines_per_hour
        print(f"\nCalculation check: {total_lines:,} lines ÷ {lines_per_hour} lines/hour = {estimated:.2f}h")
        print(f"Actual commit_hours: {commit_hours:.2f}h")
        if abs(estimated - commit_hours) > 0.1:
            print(f"WARNING: Calculation doesn't match! There may be an issue.")

if __name__ == '__main__':
    import argparse
    from pathlib import Path
    
    config = Config()
    
    parser = argparse.ArgumentParser(description='Debug card 49 commits')
    parser.add_argument('--repo-path', default='.', help='Path to git repository (default: current directory)')
    parser.add_argument('--since-date', default='2025-11-01', help='Start date (YYYY-MM-DD, default: 2025-11-01)')
    parser.add_argument('--trello-board-id', default=config.trello_board_id, help='Trello board ID (default: from config)')
    parser.add_argument('--author', help='Git author name (optional)')
    
    args = parser.parse_args()
    
    # Resolve repo path
    repo_path = str(Path(args.repo_path).resolve())
    
    if not args.trello_board_id:
        print("ERROR: Trello board ID required. Set TRELLO_BOARD_ID env var or use --trello-board-id")
        sys.exit(1)
    
    debug_card_49(repo_path, args.since_date, args.trello_board_id, args.author)

