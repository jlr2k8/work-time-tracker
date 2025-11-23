#!/usr/bin/env python3
"""
Debug script to investigate which commits were matched to a specific Trello card
"""

import sys
from pathlib import Path
from datetime import datetime

from config import Config
from trello_client import TrelloClient
from track_work import get_commits_since, get_commit_stats

def debug_card_matches(repo_path: str, since_date: str, card_number: str, 
                      author: str = None, trello_board_id: str = None):
    """
    Debug which commits were matched to a specific Trello card number
    
    Args:
        repo_path: Path to git repository
        since_date: Start date for analysis (YYYY-MM-DD)
        card_number: Trello card number (e.g., "102")
        author: Optional author filter
        trello_board_id: Optional Trello board ID
    """
    config = Config()
    
    if not config.has_trello_credentials():
        print("Error: Trello credentials not configured.", file=sys.stderr)
        sys.exit(1)
    
    trello_board_id = trello_board_id or config.trello_board_id
    if not trello_board_id:
        print("Error: Trello board ID not specified.", file=sys.stderr)
        sys.exit(1)
    
    # Initialize Trello client
    trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
    
    # Get commits
    print(f"Fetching commits since {since_date}...")
    commits = get_commits_since(repo_path, since_date, author)
    print(f"Found {len(commits)} commits\n")
    
    # Get all cards
    print("Fetching Trello cards...")
    cards = trello_client.get_cards_with_estimates(trello_board_id, since_date=None)
    print(f"Found {len(cards)} cards\n")
    
    # Find the card with the specified number
    target_card = None
    for card in cards:
        card_short_id = str(card.get('idShort', ''))
        if card_short_id == card_number:
            target_card = card
            break
    
    if not target_card:
        print(f"ERROR: Card #{card_number} not found in Trello board")
        print(f"\nAvailable card numbers (first 20):")
        for card in cards[:20]:
            short_id = card.get('idShort', 'N/A')
            name = card.get('name', 'Unknown')[:50]
            print(f"  #{short_id}: {name}")
        sys.exit(1)
    
    print(f"Found card #{card_number}: {target_card.get('name', 'Unknown')}")
    print(f"   Card ID: {target_card['id']}")
    print(f"   Estimated hours: {target_card.get('estimatedHours', 'N/A')}")
    print()
    
    # Match commits to cards
    print("Matching commits to cards...")
    # Pass author filter to exclude commits from main (by other authors) when matched by branch name
    card_commits = trello_client.match_commits_to_cards(commits, cards, expected_author=author)
    print()
    
    # Get commits matched to this card
    matched_commits = card_commits.get(target_card['id'], [])
    
    if not matched_commits:
        print(f"INFO: No commits were matched to card #{card_number}")
        print("\nThis means the card should NOT appear in your invoice.")
        print("If it did appear, there might be a bug in the invoice generation logic.")
        return
    
    print(f"WARNING: Found {len(matched_commits)} commit(s) matched to card #{card_number}:")
    print("="*70)
    
    # Show each matched commit and explain why it matched
    for i, commit in enumerate(matched_commits, 1):
        message = commit['message']
        date = commit['date']
        hash_short = commit['hash'][:8]
        lines = commit.get('lines_changed', 0)
        
        commit_author = commit.get('author', 'Unknown')
        print(f"\n{i}. Commit {hash_short} ({date}) - {lines:,} lines changed")
        print(f"   Author: {commit_author}")
        print(f"   Message: {message[:80]}")
        
        # Explain why it matched
        print("   Match reason:")
        
        # Check for explicit card reference
        card_ref = trello_client.extract_card_id_from_text(message)
        if card_ref:
            if card_ref == target_card['shortLink']:
                print(f"     [EXPLICIT] Card ID reference: {card_ref}")
            elif card_ref == target_card['id']:
                print(f"     [EXPLICIT] Card ID reference: {card_ref}")
            elif card_ref.lower() == target_card['name'].lower():
                print(f"     [EXPLICIT] Card name reference: {card_ref}")
            else:
                print(f"     [WARNING] Card reference found but doesn't match: {card_ref}")
        
        # Check fuzzy matching
        message_lower = message.lower()
        card_name_lower = target_card['name'].lower()
        
        # Extract keywords
        import re
        message_words = set(message_lower.split())
        card_words = set(re.findall(r'\b[a-z]{4,}\b', card_name_lower))
        card_words.discard('est')
        card_words.discard('hour')
        card_words.discard('hours')
        card_words.discard('mins')
        card_words.discard('minutes')
        
        matches = card_words.intersection(message_words)
        if matches:
            score = len(matches) / len(card_words) if card_words else 0
            print(f"     [FUZZY] Keyword match (score: {score:.2%})")
            print(f"       Matching words: {', '.join(sorted(matches))}")
            print(f"       Card keywords: {', '.join(sorted(card_words))}")
        
        if card_name_lower in message_lower:
            print(f"     [EXPLICIT] Exact card name found in commit message")
    
    print("\n" + "="*70)
    print(f"\nSummary:")
    print(f"  Card: #{card_number} - {target_card.get('name', 'Unknown')}")
    print(f"  Matched commits: {len(matched_commits)}")
    
    # Calculate hours
    from track_work import estimate_hours_from_commits
    hours = estimate_hours_from_commits(matched_commits)
    amount = hours * config.hourly_rate
    
    print(f"  Estimated hours: {hours:.2f}h")
    print(f"  Invoice amount: ${amount:.2f}")
    
    # Check if this looks like a false positive
    if len(matched_commits) == 1 and matched_commits[0].get('lines_changed', 0) < 50:
        print(f"\nWARNING: This looks like it might be a false positive!")
        print(f"   Only 1 commit with {matched_commits[0].get('lines_changed', 0)} lines matched.")
        print(f"   Consider checking if the commit message actually relates to this card.")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Debug which commits matched a specific Trello card',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('repo_path', help='Path to git repository')
    parser.add_argument('card_number', help='Trello card number (e.g., 102)')
    parser.add_argument('since_date', nargs='?', default='2024-11-01',
                       help='Start date for analysis (YYYY-MM-DD, default: 2024-11-01)')
    parser.add_argument('author', nargs='?', default=None,
                       help='Filter commits by author')
    parser.add_argument('trello_board_id', nargs='?', default=None,
                       help='Trello board ID (or set TRELLO_BOARD_ID env var)')
    
    args = parser.parse_args()
    
    # Validate repo path
    if not Path(args.repo_path).joinpath('.git').exists():
        print(f"Error: {args.repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
    
    debug_card_matches(
        repo_path=args.repo_path,
        since_date=args.since_date,
        card_number=args.card_number,
        author=args.author,
        trello_board_id=args.trello_board_id
    )

