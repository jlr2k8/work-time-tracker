#!/usr/bin/env python3
"""Test comment parsing for card #86"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.trello_client import TrelloClient
import re

config = Config()
trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)

# Get card #86
cards = trello_client.get_cards_with_estimates(config.trello_board_id, since_date=None)
card_86 = None
for card in cards:
    if str(card.get('idShort', '')) == '86':
        card_86 = card
        break

if not card_86:
    print("Card #86 not found")
    sys.exit(1)

# Get full details
card_details = trello_client.get_card_details(card_86['id'])
card_86.update(card_details)

print(f"Card #86: {card_86.get('name', 'Unknown')}")
print("="*70)

# Show all comments
actions = card_86.get('actions', [])
comments = [a for a in actions if a.get('type') == 'commentCard']
print(f"\nTotal comments: {len(comments)}\n")

# Test each comment
minute_patterns = [
    r'(?:^|[^\d@])(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
    r'spent\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
    r'worked\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
    r'minutes?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',
    r'\[(\d+\.?\d*)\s*(?:min|mins|minutes?)\]',
]

hour_patterns = [
    r'(?:^|[^\d@])(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
    r'spent\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
    r'worked\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
    r'hours?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',
    r'\[(\d+\.?\d*)\s*h(?:ours?|rs?)\]',
]

for i, comment in enumerate(comments, 1):
    text = comment.get('data', {}).get('text', '')
    date = comment.get('date', 'Unknown')
    print(f"Comment {i} [{date}]:")
    print(f"  Text: {text}")
    
    # Try hour patterns first
    matched = False
    for pattern in hour_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            hours = float(matches[0])
            print(f"  -> Matched HOUR pattern: {pattern}")
            print(f"  -> Hours: {hours}h")
            matched = True
            break
    
    if not matched:
        # Try minute patterns
        for pattern in minute_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                minutes = float(matches[0])
                hours = round(minutes / 60.0, 2)
                print(f"  -> Matched MINUTE pattern: {pattern}")
                print(f"  -> Minutes: {minutes}, Hours: {hours}h")
                matched = True
                break
    
    if not matched:
        print(f"  -> NO MATCH")
    print()

# Test the actual function
print("="*70)
print("Testing extract_hours_from_comments() function:")
print("="*70)
hours = trello_client.extract_hours_from_comments(card_86, "2025-11-10")
print(f"\nTotal hours found: {hours}h")

