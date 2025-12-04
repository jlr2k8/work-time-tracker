#!/usr/bin/env python3
"""
Check which cards assigned to you don't have estimated hours in their titles
"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.trello_client import TrelloClient

def check_missing_estimates():
	"""Find cards assigned to you that don't have estimated hours in their titles"""
	config = Config()
	
	if not config.has_trello_credentials():
		print("Error: Trello API credentials not configured")
		print("Set TRELLO_API_KEY and TRELLO_API_TOKEN environment variables")
		return
	
	if not config.trello_board_id:
		print("Error: Trello board ID not configured")
		print("Set TRELLO_BOARD_ID environment variable")
		return
	
	if not config.trello_member_id:
		print("Error: Trello member ID not configured")
		print("Set TRELLO_MEMBER_ID environment variable")
		return
	
	trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
	
	# Get all cards from the board
	print("Fetching cards from board...")
	all_cards = trello_client.get_board_cards(config.trello_board_id)
	
	# Filter to WIP/Done lists
	lists = trello_client.get_board_lists(config.trello_board_id)
	wip_done_lists = {list_id: name for list_id, name in lists.items() 
					  if any(keyword in name.upper() for keyword in ['WIP', 'DONE', 'COMPLETE', 'FINISHED'])}
	
	if not wip_done_lists:
		print("WARNING: No 'WIP' or 'Done' lists found. Checking all cards.")
		filtered_cards = all_cards
	else:
		filtered_cards = [card for card in all_cards if card.get('idList') in wip_done_lists]
		print(f"Found {len(filtered_cards)} cards in WIP/Done lists")
	
	# Get cards assigned to you
	print(f"\nChecking cards assigned to you (member ID: {config.trello_member_id[:8]}...)...")
	assigned_cards = []
	cards_without_estimates = []
	
	for card in filtered_cards:
		try:
			# Get full card details to check members and extract estimates
			full_card = trello_client.get_card_details(card['id'])
			
			# Check if assigned to you
			if config.trello_member_id in full_card.get('idMembers', []):
				assigned_cards.append(full_card)
				
				# Try to extract estimated hours
				estimated = trello_client.extract_estimated_hours(full_card)
				
				if estimated is None:
					# No estimate found
					card_id_short = full_card.get('idShort', '?')
					card_name = full_card.get('name', 'Unknown')
					card_url = f"https://trello.com/c/{full_card.get('shortLink', '')}"
					
					cards_without_estimates.append({
						'id': card_id_short,
						'name': card_name,
						'url': card_url
					})
		except Exception as e:
			print(f"  Warning: Error processing card {card.get('idShort', '?')}: {e}")
			continue
	
	print(f"\n{'='*70}")
	print(f"Summary:")
	print(f"  Total cards assigned to you: {len(assigned_cards)}")
	print(f"  Cards WITHOUT estimated hours in title: {len(cards_without_estimates)}")
	print(f"{'='*70}\n")
	
	if cards_without_estimates:
		print("Cards missing estimated hours:")
		print("-" * 70)
		for card in sorted(cards_without_estimates, key=lambda x: int(x['id']) if x['id'].isdigit() else 9999):
			print(f"  #{card['id']}: {card['name'][:60]}")
			print(f"    URL: {card['url']}")
			print()
	else:
		print("✓ All assigned cards have estimated hours in their titles!")
	
	return cards_without_estimates

if __name__ == '__main__':
	check_missing_estimates()

