#!/usr/bin/env python3
"""
Configuration management for work time tracker
"""

import os
from pathlib import Path
from typing import Optional

try:
	from dotenv import load_dotenv
	load_dotenv()  # Load .env file if it exists
except ImportError:
	pass  # dotenv is optional, fall back to environment variables only

class Config:
	"""Configuration for work time tracker"""
	
	def __init__(self):
		"""Load configuration from environment variables or .env file"""
		# Trello API credentials
		self.trello_api_key = os.getenv('TRELLO_API_KEY', '')
		self.trello_api_token = os.getenv('TRELLO_API_TOKEN', '')
		
		# Trello board ID (can be overridden via command line)
		self.trello_board_id = os.getenv('TRELLO_BOARD_ID', '')
		
		# Hourly rate
		self.hourly_rate = float(os.getenv('HOURLY_RATE', '80.0'))
		
		# Excluded card numbers (comma-separated list, e.g., "102,103,104")
		excluded_cards_str = os.getenv('EXCLUDED_CARDS', '')
		self.excluded_cards = [c.strip() for c in excluded_cards_str.split(',') if c.strip()] if excluded_cards_str else []
		
		# Invoice generator settings
		self.sender_name = os.getenv('SENDER_NAME', 'Your Name')
		self.sender_address = os.getenv('SENDER_ADDRESS', '123 Main St, City, ST 12345')
		self.sender_phone = os.getenv('SENDER_PHONE', '555-555-5555')
		self.sender_email = os.getenv('SENDER_EMAIL', 'your.email@example.com')
		self.recipient_name = os.getenv('RECIPIENT_NAME', 'Client Name')
		self.invoice_prefix = os.getenv('INVOICE_PREFIX', 'INV')
		
		# Trello member ID (for filtering cards assigned to you)
		self.trello_member_id = os.getenv('TRELLO_MEMBER_ID', '')
	
	def has_trello_credentials(self) -> bool:
		"""Check if Trello credentials are configured"""
		return bool(self.trello_api_key and self.trello_api_token)
	
	def validate(self) -> tuple[bool, Optional[str]]:
		"""
		Validate configuration
		
		Returns:
			(is_valid, error_message)
		"""
		if not self.has_trello_credentials():
			return False, "Trello API credentials not configured. Set TRELLO_API_KEY and TRELLO_API_TOKEN environment variables or create a .env file."
		
		return True, None
