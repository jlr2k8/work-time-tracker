#!/usr/bin/env python3
"""
Debug script to show exactly what hours are found for a specific card
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from trello_client import TrelloClient

config = Config()
trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)

# Get card #99
cards = trello_client.get_cards_with_estimates(config.trello_board_id, since_date=None)
card_99 = None
for card in cards:
    if str(card.get('idShort', '')) == '99':
        card_99 = card
        break

if not card_99:
    print("Card #99 not found")
    sys.exit(1)

# Get full details
card_details = trello_client.get_card_details(card_99['id'])
card_99.update(card_details)

print(f"Card #99: {card_99.get('name', 'Unknown')}")
print(f"="*70)

# Show ALL comments
actions = card_99.get('actions', [])
comments = [a for a in actions if a.get('type') == 'commentCard']
print(f"\nTotal comments found: {len(comments)}")

# Show comments with dates
print("\nAll comments (with dates):")
for i, comment in enumerate(comments, 1):
    text = comment.get('data', {}).get('text', '')
    date = comment.get('date', 'Unknown')
    print(f"  {i}. [{date}] {text[:80]}")

# Test with since_date filter
since_date = "2025-11-10"
print(f"\n" + "="*70)
print(f"Testing with since_date filter: {since_date}")
print("="*70)

hours_with_filter = trello_client.extract_hours_from_comments(card_99, since_date)
hours_without_filter = trello_client.extract_hours_from_comments(card_99, None)

print(f"\nHours found WITH date filter ({since_date}): {hours_with_filter}h")
print(f"Hours found WITHOUT date filter: {hours_without_filter}h")
print(f"\nDifference: {hours_without_filter - hours_with_filter}h")

