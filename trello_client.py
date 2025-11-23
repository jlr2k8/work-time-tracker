#!/usr/bin/env python3
"""
Trello API Client - Fetch cards, extract estimates, and match with commits
"""

import requests
import os
from typing import List, Dict, Optional
from datetime import datetime
import re

try:
	from dateutil import parser as date_parser
except ImportError:
	# Fallback if dateutil not available
	date_parser = None

class TrelloClient:
	"""Client for interacting with Trello API"""
	
	def __init__(self, api_key: str, api_token: str):
		"""
		Initialize Trello client
		
		Args:
			api_key: Trello API key
			api_token: Trello API token
		"""
		self.api_key = api_key
		self.api_token = api_token
		self.base_url = "https://api.trello.com/1"
	
	def _request(self, endpoint: str, params: Dict = None, timeout: int = 10) -> Dict:
		"""Make a request to Trello API"""
		if params is None:
			params = {}
		params.update({
			'key': self.api_key,
			'token': self.api_token
		})
		
		url = f"{self.base_url}/{endpoint}"
		response = requests.get(url, params=params, timeout=timeout)
		response.raise_for_status()
		return response.json()
	
	def get_board_lists(self, board_id: str) -> Dict[str, str]:
		"""
		Get all lists from a board, mapping list ID to list name
		
		Returns:
			Dictionary mapping list ID to list name
		"""
		lists = self._request(f"boards/{board_id}/lists")
		return {lst['id']: lst['name'] for lst in lists}
	
	def get_board_cards(self, board_id: str, since_date: str = None) -> List[Dict]:
		"""
		Get all cards from a board, optionally filtered by date
		
		Args:
			board_id: Trello board ID
			since_date: Only get cards modified since this date (YYYY-MM-DD)
		
		Returns:
			List of card dictionaries (includes idList field)
		"""
		params = {'filter': 'all'}
		if since_date:
			params['since'] = since_date
		
		cards = self._request(f"boards/{board_id}/cards", params)
		return cards
	
	def get_card_details(self, card_id: str) -> Dict:
		"""Get full details of a card including custom fields"""
		card = self._request(f"cards/{card_id}")
		
		# Get custom fields if available
		try:
			custom_fields = self._request(f"cards/{card_id}/customFieldItems")
			card['customFields'] = custom_fields
		except:
			card['customFields'] = []
		
		# Get members assigned to card
		try:
			members = self._request(f"cards/{card_id}/members")
			card['members'] = members
			card['idMembers'] = [m.get('id') for m in members]
		except:
			card['members'] = []
			card['idMembers'] = []
		
		# Get actions (for date tracking)
		try:
			actions = self._request(f"cards/{card_id}/actions", {'filter': 'updateCard,commentCard'})
			card['actions'] = actions
		except:
			card['actions'] = []
		
		return card
	
	def get_my_assigned_cards(self, board_id: str, my_member_id: str, since_date: str = None) -> List[Dict]:
		"""
		Get cards assigned to a specific member
		
		Args:
			board_id: Trello board ID
			my_member_id: Trello member ID to filter by
			since_date: Only get cards modified since this date (YYYY-MM-DD)
		
		Returns:
			List of cards assigned to the member
		"""
		all_cards = self.get_board_cards(board_id, since_date)
		assigned_cards = []
		
		for card in all_cards:
			# Get full card details to check members
			try:
				full_card = self.get_card_details(card['id'])
				if my_member_id in full_card.get('idMembers', []):
					assigned_cards.append(full_card)
			except:
				continue
		
		return assigned_cards
	
	def extract_hours_from_comments(self, card: Dict, since_date: str = None) -> float:
		"""
		Extract hours from Trello card comments
		Looks for patterns like: "1.5h", "2 hours", "spent 1.5h", etc.
		
		Args:
			card: Card dictionary with 'actions' containing comments
			since_date: Only count comments since this date (YYYY-MM-DD)
		
		Returns:
			Total hours found in comments
		"""
		total_hours = 0.0
		actions = card.get('actions', [])
		
		# Filter to only comment actions
		comments = [a for a in actions if a.get('type') == 'commentCard']
		
		# Filter by date if provided
		if since_date and date_parser:
			try:
				since_dt = datetime.strptime(since_date, '%Y-%m-%d')
				filtered_comments = []
				for c in comments:
					comment_date_str = c.get('date', '')
					if comment_date_str:
						try:
							comment_dt = date_parser.parse(comment_date_str)
							if comment_dt.date() >= since_dt.date():
								filtered_comments.append(c)
						except:
							# If date parsing fails, include the comment
							filtered_comments.append(c)
				comments = filtered_comments
			except ValueError:
				pass  # Invalid date format, include all comments
		
		# Patterns to match hours in comments (flexible)
		# First try hours patterns - avoid matching user IDs, card IDs, etc.
		# Use word boundaries and context to avoid false positives
		hour_patterns = [
			r'(?:^|[^\d@])(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',  # "1.5h", "2 hours" (not part of ID)
			r'spent\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',  # "spent 1.5h"
			r'worked\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',  # "worked 2h"
			r'hours?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',  # "hours: 1.5"
			r'\[(\d+\.?\d*)\s*h(?:ours?|rs?)\]',  # "[1.5h]"
		]
		
		# Then try minutes patterns (convert to hours)
		minute_patterns = [
			r'(?:^|[^\d@])(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',  # "30 min" (not part of ID)
			r'spent\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',  # "spent 30 min"
			r'worked\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',  # "worked 30 min"
			r'minutes?:\s*(\d+\.?\d*)(?:\s|$|[^\d])',  # "minutes: 30"
			r'\[(\d+\.?\d*)\s*(?:min|mins|minutes?)\]',  # "[30 min]"
		]
		
		for comment in comments:
			text = comment.get('data', {}).get('text', '')
			if not text:
				continue
			
			# Try hours patterns first
			for pattern in hour_patterns:
				matches = re.findall(pattern, text, re.IGNORECASE)
				if matches:
					try:
						hours = float(matches[0])
						total_hours += hours
						break  # Only count once per comment
					except ValueError:
						continue
			else:
				# If no hours found, try minutes patterns
				for pattern in minute_patterns:
					matches = re.findall(pattern, text, re.IGNORECASE)
					if matches:
						try:
							minutes = float(matches[0])
							hours = round(minutes / 60.0, 2)  # Convert to hours
							total_hours += hours
							break  # Only count once per comment
						except ValueError:
							continue
		
		return round(total_hours, 2)
	
	def extract_estimated_hours(self, card: Dict) -> Optional[float]:
		"""
		Extract estimated hours from a Trello card
		Looks in: custom fields, labels, description, card name
		Supports formats like: "Est 1 hour", "Est 30 mins", "2h", "1.5 hours", etc.
		"""
		# Check custom fields for hours estimate
		for field in card.get('customFields', []):
			field_name = field.get('name', '').lower()
			if 'hour' in field_name or 'estimate' in field_name or 'time' in field_name:
				value = field.get('value', {})
				if isinstance(value, dict):
					number = value.get('number')
					if number:
						return float(number)
		
		# Check labels for hour estimates (e.g., "2h", "3.5h")
		for label in card.get('labels', []):
			label_name = label.get('name', '').lower()
			# Look for patterns like "2h", "3.5h", "1.5 hours"
			match = re.search(r'(\d+\.?\d*)\s*h(?:ours?)?', label_name)
			if match:
				return float(match.group(1))
		
		# Check description for hour estimates
		desc = card.get('desc', '')
		if desc:
			# Look for patterns like "Est: 2h", "Estimated: 3.5 hours", etc.
			patterns = [
				r'est(?:imated)?:?\s*(\d+\.?\d*)\s*h(?:ours?)?',
				r'(\d+\.?\d*)\s*h(?:ours?)?\s*est(?:imated)?',
				r'hours?:\s*(\d+\.?\d*)',
			]
			for pattern in patterns:
				match = re.search(pattern, desc, re.IGNORECASE)
				if match:
					return float(match.group(1))
		
		# Check card name for hour estimates - enhanced patterns
		name = card.get('name', '')
		if name:
			# Pattern 1: "(Est 1 hour)" or "(Est 30 mins)" - handle minutes conversion
			match = re.search(r'\(est\s+(\d+)\s*(?:hour|hr|h)\)', name, re.IGNORECASE)
			if match:
				return float(match.group(1))
			
			# Pattern 2: "(Est 30 mins)" or "(Est 45 minutes)" - convert to hours
			match = re.search(r'\(est\s+(\d+)\s*(?:min|mins|minutes?)\)', name, re.IGNORECASE)
			if match:
				minutes = float(match.group(1))
				return round(minutes / 60.0, 2)
			
			# Pattern 3: "[2h]" or "[1.5 hours]"
			match = re.search(r'\[(\d+\.?\d*)\s*h(?:ours?)?\]', name, re.IGNORECASE)
			if match:
				return float(match.group(1))
			
			# Pattern 4: "Est: 2h" or "Est 3 hours" (without parentheses)
			match = re.search(r'est:?\s*(\d+\.?\d*)\s*h(?:ours?)?', name, re.IGNORECASE)
			if match:
				return float(match.group(1))
		
		return None
	
	def extract_card_id_from_text(self, text: str) -> Optional[str]:
		"""
		Extract Trello card ID or short link from text (commit message, etc.)
		Looks for patterns like: [Trello-abc123], #abc123, or full card URLs
		"""
		# Pattern for short card ID (8 chars, alphanumeric)
		short_id_pattern = r'\[?Trello[:\-]?([a-zA-Z0-9]{8})\]?'
		match = re.search(short_id_pattern, text, re.IGNORECASE)
		if match:
			return match.group(1)
		
		# Pattern for card URL
		url_pattern = r'trello\.com/c/([a-zA-Z0-9]+)'
		match = re.search(url_pattern, text, re.IGNORECASE)
		if match:
			return match.group(1)
		
		# Pattern for card name reference (looks for card title in brackets)
		# This is less reliable but common
		name_pattern = r'\[([^\]]+)\]'
		matches = re.findall(name_pattern, text)
		# Return first match - caller can use this to search by name
		if matches:
			return matches[0]  # This will be a name, not an ID
	
	def match_commits_to_cards(self, commits: List[Dict], cards: List[Dict], expected_author: str = None) -> Dict[str, List[Dict]]:
		"""
		Match git commits to Trello cards
		
		Args:
			commits: List of commit dictionaries with 'hash', 'message', 'author', 'email', 'branches', etc.
			cards: List of Trello card dictionaries
			expected_author: Optional author name to filter commits. If provided, commits by other authors
				matched only by branch name will be excluded (to avoid counting commits from main branch
				that were merged into your feature branch)
		
		Returns:
			Dictionary mapping card IDs to lists of matching commits
			Each commit dict will have a '_match_type' field: 'explicit' or 'fuzzy'
		"""
		card_commits: Dict[str, List[Dict]] = {}
		
		# Create a lookup by card ID, short ID, name, and card number
		cards_by_id = {card['id']: card for card in cards}
		cards_by_short_id = {card['shortLink']: card for card in cards}
		cards_by_name = {card['name'].lower(): card for card in cards}
		# Create lookup by card number (idShort) - e.g., "99" -> card
		cards_by_number = {str(card.get('idShort', '')): card for card in cards if card.get('idShort')}
		
		print(f"Matching {len(commits)} commits to {len(cards)} cards...")
		if expected_author:
			print(f"Filtering: Only commits by '{expected_author}' will be matched by branch name")
		
		excluded_by_author = 0
		
		for i, commit in enumerate(commits):
			message = commit['message']
			branches = commit.get('branches', [])  # Get branch names from commit
			commit_author = commit.get('author', '')
			
			# Try to find matching card
			matched_card = None
			
			# PRIORITY 1: Check branch names for card numbers (most reliable!)
			# Branch names like "feature/99-vendor-estimate-creation" are explicit
			match_type = None
			matched_by_branch = False
			if branches:
				for branch in branches:
					# Look for card number in branch name (e.g., feature/99-, 99-vendor, etc.)
					branch_match = re.search(r'[/-](\d+)[/-]', branch.lower())
					if branch_match:
						card_num = branch_match.group(1)
						if card_num in cards_by_number:
							# If expected_author is provided, check that this commit is by the expected author
							# This prevents commits from main (by other authors) from being matched
							# when you merge main into your feature branch
							if expected_author:
								# Normalize author names for comparison (case-insensitive, partial match)
								author_lower = commit_author.lower()
								expected_lower = expected_author.lower()
								# Check if expected author name appears in commit author name
								# This handles variations like "John Doe" vs "John" or "jdoe" vs "John Doe"
								if expected_lower not in author_lower and author_lower not in expected_lower:
									# Check if any part of expected author matches
									expected_parts = expected_lower.split()
									author_parts = author_lower.split()
									if not any(ep in author_lower or ap in expected_lower for ep in expected_parts for ap in author_parts):
										excluded_by_author += 1
										continue  # Skip this match - commit is by different author
							matched_card = cards_by_number[card_num]
							match_type = 'explicit'
							matched_by_branch = True
							break
			
			# PRIORITY 2: Check for card ID in commit message
			if not matched_card:
				card_ref = self.extract_card_id_from_text(message)
				if card_ref:
					# Try as short ID first
					if card_ref in cards_by_short_id:
						matched_card = cards_by_short_id[card_ref]
						match_type = 'explicit'
					# Try as full ID
					elif card_ref in cards_by_id:
						matched_card = cards_by_id[card_ref]
						match_type = 'explicit'
					# Try as card name
					elif card_ref.lower() in cards_by_name:
						matched_card = cards_by_name[card_ref.lower()]
						match_type = 'explicit'
			
			# PRIORITY 3: Check for card number in commit message (#99, T99)
			if not matched_card:
				# Look for patterns like #99, T99 in commit message
				card_number_patterns = [
					r'#(\d+)',  # #99
					r'\bT(\d+)\b',  # T99 (word boundary to avoid matching T1234)
				]
				for pattern in card_number_patterns:
					match = re.search(pattern, message, re.IGNORECASE)
					if match:
						card_num = match.group(1)
						if card_num in cards_by_number:
							matched_card = cards_by_number[card_num]
							match_type = 'explicit'
							break
			
			# If no direct match, try fuzzy matching on card names
			if not matched_card:
				message_lower = message.lower()
				# Split on spaces, slashes, and dashes to extract all words
				# This handles "FEATURE/WIP" -> ["feature", "wip"] and "T1-T2" -> ["t1", "t2"]
				message_words = set()
				for word in message_lower.split():
					# Split on / and - as well
					parts = re.split(r'[/-]', word)
					message_words.update(parts)
				# Also add the original words in case they're meaningful
				message_words.update(message_lower.split())
				
				# Score cards by keyword matches
				best_match = None
				best_score = 0
				
				# Sort cards by name for deterministic matching
				for card_name, card in sorted(cards_by_name.items()):
					if len(card_name) < 5 or len(card_name) > 100:
						continue
					
					# Extract key words from card name (remove common words, numbers, etc.)
					card_words = set(re.findall(r'\b[a-z]{4,}\b', card_name.lower()))
					card_words.discard('est')  # Remove "est", "estimated", etc.
					card_words.discard('hour')
					card_words.discard('hours')
					card_words.discard('mins')
					card_words.discard('minutes')
					card_words.discard('phase')  # Remove common project words
					card_words.discard('including')
					card_words.discard('max')
					
					if not card_words:
						continue
					
					# Count matching words
					matches = card_words.intersection(message_words)
					if matches:
						# Prioritize cards with MORE matching keywords, not just percentage
						# Use a combination: percentage + absolute match count
						percentage_score = len(matches) / len(card_words)  # Percentage of card words found
						match_count_score = len(matches) * 0.15  # Bonus for each match (0.15 per match)
						score = percentage_score + match_count_score
						
						# Bonus for exact phrase match
						if card_name in message_lower:
							score += 0.5
						
						# Bonus for task identifier match (T5, T6, etc.)
						task_match = re.search(r'\(t\d+\)', card_name.lower())
						if task_match:
							task_id = task_match.group(0)
							if task_id in message_lower:
								score += 0.3
						
						# HEAVY bonus for multiple unique keyword matches (more specific = better match)
						# This prioritizes cards with more matching keywords
						if len(matches) >= 3:
							score += 0.5  # Strong match bonus
						elif len(matches) >= 2:
							score += 0.3  # Moderate match bonus
						
						# Bonus for matching highly specific keywords (stronger signal)
						specific_keywords = {'vendor', 'estimate', 'creation', 'feature'}
						specific_matches = matches.intersection(specific_keywords)
						if len(specific_matches) >= 2:
							score += 0.2  # Bonus for matching multiple specific keywords
						
						# Require at least 30% match OR 2+ matching words (more permissive to catch valid work)
						# This ensures we don't miss legitimate matches
						if score > best_score and (score > 0.3 or len(matches) >= 2):
							best_score = score
							best_match = card
				
				if best_match:
					matched_card = best_match
					match_type = 'fuzzy'
			
			if matched_card:
				card_id = matched_card['id']
				if card_id not in card_commits:
					card_commits[card_id] = []
				# Add match type to commit for filtering later
				commit_with_match = commit.copy()
				commit_with_match['_match_type'] = match_type or 'fuzzy'
				card_commits[card_id].append(commit_with_match)
			
			# Progress every 10 commits
			if (i + 1) % 10 == 0:
				print(f"  Matched {i + 1}/{len(commits)} commits...")
		
		if excluded_by_author > 0:
			print(f"  Excluded {excluded_by_author} commit(s) matched by branch name but authored by someone else")
		print(f"Done matching. Found {len(card_commits)} cards with matching commits.")
		return card_commits
	
	def get_cards_with_estimates(self, board_id: str, since_date: str = None) -> List[Dict]:
		"""
		Get cards with extracted estimated hours (basic info only, no comments)
		Use get_card_details_for_matched() to fetch full details only for matched cards.
		
		Returns:
			List of cards with 'estimatedHours' field added (basic info only)
		"""
		cards = self.get_board_cards(board_id, since_date)
		print(f"Found {len(cards)} Trello cards, extracting estimates...")
		
		# Extract estimates from basic card info (fast - no API calls needed)
		for card in cards:
			card['estimatedHours'] = self.extract_estimated_hours(card)
			# Initialize actions as empty - will be populated later if needed
			card['actions'] = []
		
		print(f"Done extracting estimates.")
		return cards
	
	def get_card_details_for_matched(self, card_ids: List[str]) -> Dict[str, Dict]:
		"""
		Fetch full card details (including comments) only for matched cards.
		Uses parallel requests to speed up API calls.
		
		Args:
			card_ids: List of card IDs to fetch details for
		
		Returns:
			Dictionary mapping card_id to full card details
		"""
		if not card_ids:
			return {}
		
		print(f"Fetching full details for {len(card_ids)} matched cards...")
		
		# Use threading to parallelize API calls
		from concurrent.futures import ThreadPoolExecutor, as_completed
		
		card_details = {}
		
		def fetch_card(card_id: str) -> tuple[str, Dict]:
			try:
				details = self.get_card_details(card_id)
				return (card_id, details)
			except Exception as e:
				print(f"  Warning: Failed to fetch details for card {card_id}: {e}")
				return (card_id, {'actions': []})
		
		# Use ThreadPoolExecutor to parallelize requests (max 5 concurrent to avoid rate limits)
		with ThreadPoolExecutor(max_workers=5) as executor:
			futures = {executor.submit(fetch_card, card_id): card_id for card_id in card_ids}
			
			completed = 0
			for future in as_completed(futures):
				card_id, details = future.result()
				card_details[card_id] = details
				completed += 1
				if completed % 10 == 0:
					print(f"  Fetched {completed}/{len(card_ids)} cards...")
		
		print(f"Done fetching card details.")
		return card_details
