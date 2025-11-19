#!/usr/bin/env python3
"""
Extract Trello card links for invoice line items
"""

import sys
import os
from pathlib import Path

# Add the current directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

from track_work import get_commit_stats, generate_invoice_line_items, extract_task_number
from config import Config
from trello_client import TrelloClient

def get_card_links_for_invoice(since_date: str, repo_path: str = '.', author: str = None, task_numbers: list = None):
	"""
	Get Trello card links for invoice line items
	
	Args:
		since_date: Date to start tracking from (YYYY-MM-DD)
		repo_path: Path to git repository (default: current directory)
		author: Git author to filter commits (optional)
		task_numbers: Optional list of task numbers to filter (e.g., ['60', '82', '83', '86'])
	"""
	config = Config()
	
	if not config.trello_api_key or not config.trello_api_token:
		print("Error: Trello API credentials not configured")
		print("Set TRELLO_API_KEY and TRELLO_API_TOKEN environment variables")
		return
	
	if not config.trello_board_id:
		print("Error: Trello board ID not configured")
		print("Set TRELLO_BOARD_ID environment variable")
		return
	
	trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
	
	# Get commit stats with Trello integration
	print(f"Fetching commit stats since {since_date}...")
	stats = get_commit_stats(
		repo_path=repo_path,
		since_date=since_date,
		author=author,
		trello_client=trello_client,
		trello_board_id=config.trello_board_id,
		config=config
	)
	
	if not stats.get('trello_enabled'):
		print("Error: Trello integration not enabled or failed")
		return
	
	# Generate line items
	line_items = generate_invoice_line_items(stats, config)
	
	if not line_items:
		print("No line items found")
		return
	
	# Get matched cards data
	details = stats.get('estimation_details', {})
	matched_cards = details.get('matched_cards', [])
	
	# Create a mapping from task number to card
	task_to_card = {}
	for match in matched_cards:
		card = match['card']
		task_num = extract_task_number(card) or 'N/A'
		task_to_card[task_num] = card
	
	# Filter line items if task numbers specified
	if task_numbers:
		line_items = [item for item in line_items if item['task_number'] in task_numbers]
	
	# Print card links
	print("\n" + "="*70)
	print("TRELLO CARD LINKS FOR INVOICE LINE ITEMS")
	print("="*70)
	
	for item in line_items:
		task_num = item['task_number']
		description = item['description']
		amount = item['amount']
		
		if task_num in task_to_card:
			card = task_to_card[task_num]
			short_link = card.get('shortLink', '')
			card_name = card.get('name', 'Unknown')
			
			if short_link:
				card_url = f"https://trello.com/c/{short_link}"
				print(f"\n#{task_num} - {description[:60]}")
				print(f"  Card: {card_name[:60]}")
				print(f"  URL: {card_url}")
				print(f"  Amount: ${amount:,.2f}")
			else:
				print(f"\n#{task_num} - {description[:60]}")
				print(f"  Card: {card_name[:60]}")
				print(f"  URL: (No shortLink available)")
				print(f"  Amount: ${amount:,.2f}")
		else:
			print(f"\n#{task_num} - {description[:60]}")
			print(f"  (Card not found in matched cards)")
			print(f"  Amount: ${amount:,.2f}")
	
	print("\n" + "="*70)

if __name__ == '__main__':
	# Default to last 30 days if no date provided
	import datetime
	from pathlib import Path
	
	# Parse arguments: [since_date] [task_numbers] [repo_path] [author]
	since_date = None
	task_numbers = None
	repo_path = '.'
	author = None
	
	if len(sys.argv) > 1:
		since_date = sys.argv[1]
	if len(sys.argv) > 2:
		task_numbers = sys.argv[2].split(',')
	if len(sys.argv) > 3:
		repo_path = sys.argv[3]
	if len(sys.argv) > 4:
		author = sys.argv[4]
	
	# Default to 30 days ago if no date provided
	if not since_date:
		since_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
	
	# Default repo_path to current directory if not a git repo
	if not Path(repo_path).joinpath('.git').exists():
		# Try current directory
		if Path('.').joinpath('.git').exists():
			repo_path = '.'
		else:
			print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
			sys.exit(1)
	
	print(f"Getting card links for invoice items since {since_date}")
	if task_numbers:
		print(f"Filtering to task numbers: {', '.join(task_numbers)}")
	
	get_card_links_for_invoice(since_date, repo_path, author, task_numbers)

