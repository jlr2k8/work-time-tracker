#!/usr/bin/env python3
from config import Config
from trello_client import TrelloClient

config = Config()
tc = TrelloClient(config.trello_api_key, config.trello_api_token)

# Get all cards
cards = tc.get_board_cards(config.trello_board_id)

# Filter to WIP/Done lists
lists = tc.get_board_lists(config.trello_board_id)
wip_done_lists = {list_id: name for list_id, name in lists.items() 
                  if any(keyword in name.upper() for keyword in ['WIP', 'DONE', 'COMPLETE', 'FINISHED'])}
filtered_cards = [card for card in cards if card.get('idList') in wip_done_lists]

# Count cards assigned to member
member_id = config.trello_member_id
if not member_id:
    print("Error: TRELLO_MEMBER_ID not set in .env file")
    exit(1)

assigned_count = 0

for card in filtered_cards:
    details = tc.get_card_details(card['id'])
    if member_id in details.get('idMembers', []):
        assigned_count += 1

print(f"Cards assigned to you: {assigned_count} out of {len(filtered_cards)} cards in WIP/Done lists")
