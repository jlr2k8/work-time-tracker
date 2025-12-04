#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Work Time Tracker - Analyze git commits and Trello tasks to estimate billable hours
"""

import subprocess
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json

# Helper function to sanitize text for safe printing (removes emojis, special characters)
def sanitize_text(text: str) -> str:
	"""Remove emojis, em dashes, and other problematic Unicode characters"""
	if not isinstance(text, str):
		return str(text)
	
	# Remove em dashes (—) and en dashes (–), replace with regular hyphens
	text = text.replace('—', '-').replace('–', '-')
	
	# Remove emojis and other non-ASCII characters that cause encoding issues
	# Keep basic ASCII printable characters (32-126) plus common punctuation
	sanitized = ''
	for char in text:
		# Keep ASCII printable characters
		if 32 <= ord(char) <= 126:
			sanitized += char
		# Keep common Unicode punctuation that's safe
		elif char in ['\n', '\t', '\r']:
			sanitized += char
		# Replace everything else with a space or hyphen if it looks like punctuation
		elif char in ['…', '…']:  # Ellipsis
			sanitized += '...'
		else:
			# For other Unicode, try to keep if it's a common character, otherwise skip
			try:
				char.encode('ascii')
				sanitized += char
			except UnicodeEncodeError:
				# Skip emojis and other problematic characters
				pass
	
	return sanitized

from .config import Config
from .trello_client import TrelloClient
from .invoice_generator import InvoiceGenerator, create_invoice_from_tracking_data
import re

def run_git_command(repo_path: str, *args: str) -> str:
	"""Run a git command and return output"""
	try:
		result = subprocess.run(
			['git', '-C', repo_path] + list(args),
			capture_output=True,
			text=True,
			check=True
		)
		return result.stdout.strip()
	except subprocess.CalledProcessError as e:
		print(f"Error running git command: {e}", file=sys.stderr)
		return ""

def get_commit_line_stats(repo_path: str, commit_hash: str) -> Dict[str, int]:
	"""Get line statistics (additions, deletions) for a commit, excluding auto-generated files"""
	# Files to exclude (dependencies, auto-generated, etc.)
	exclude_patterns = [
		'package-lock.json',
		'yarn.lock',
		'pnpm-lock.yaml',
		'node_modules/',
		'.min.js',
		'.min.css',
		'dist/',
		'build/',
		'.bundle',
		'vendor/',
		'composer.lock',
		'Pipfile.lock',
		'poetry.lock',
		'.pyc',
		'__pycache__/',
		'.class',
		'.jar',
		'.war',
		'.dll',
		'.exe',
		'.so',
		'.dylib',
		'.log',
		'.cache',
		'.tmp',
		'.temp',
		'.swp',
		'.swo',
		'~',
		'.DS_Store',
		'Thumbs.db'
	]
	
	try:
		# Use --numstat to get additions and deletions per file
		result = subprocess.run(
			['git', '-C', repo_path, 'show', '--numstat', '--format=', commit_hash],
			capture_output=True,
			text=True,
			check=True
		)
		
		total_additions = 0
		total_deletions = 0
		excluded_files = []
		
		for line in result.stdout.strip().split('\n'):
			if not line:
				continue
			parts = line.split('\t')
			if len(parts) >= 3:
				try:
					additions = int(parts[0]) if parts[0] != '-' else 0
					deletions = int(parts[1]) if parts[1] != '-' else 0
					filename = parts[2]
					
					# Check if file should be excluded
					should_exclude = any(pattern in filename for pattern in exclude_patterns)
					
					if should_exclude:
						excluded_files.append(filename)
					else:
						total_additions += additions
						total_deletions += deletions
				except (ValueError, IndexError):
					continue
		
		return {
			'additions': total_additions,
			'deletions': total_deletions,
			'total_changed': total_additions + total_deletions,
			'excluded_files': excluded_files
		}
	except subprocess.CalledProcessError:
		return {'additions': 0, 'deletions': 0, 'total_changed': 0, 'excluded_files': []}

def get_commits_since(repo_path: str, since_date: str, author: str = None) -> List[Dict]:
	"""
	Get commits since a date from ALL branches, optionally filtered by author.
	Uses --all to capture work from feature branches that haven't been merged yet.
	Deduplicates by commit hash to avoid counting the same commit twice.
	"""
	format_str = "%H|%an|%ae|%ad|%s"
	
	# Use --all to get commits from all branches (including feature branches)
	# This captures work that hasn't been merged to main yet
	cmd = ['log', '--all', f'--since={since_date}', f'--format={format_str}', '--date=short']
	
	if author:
		# Git author filter - if it contains |, use grep instead
		if '|' in author:
			# Use grep to filter by multiple authors
			cmd.extend(['--pretty=format:%H|%an|%ae|%ad|%s', '--date=short'])
			output = run_git_command(repo_path, *cmd)
			if output:
				# Filter by author names
				author_names = [a.strip() for a in author.split('|')]
				filtered_lines = []
				for line in output.split('\n'):
					if not line:
						continue
					parts = line.split('|', 4)
					if len(parts) == 5:
						commit_author = parts[1]
						if any(a.lower() in commit_author.lower() for a in author_names):
							filtered_lines.append(line)
				output = '\n'.join(filtered_lines)
		else:
			cmd.extend(['--author', author])
			output = run_git_command(repo_path, *cmd)
	else:
		output = run_git_command(repo_path, *cmd)
	
	commits = []
	seen_hashes = set()  # Deduplicate by commit hash
	
	if output:
		for line in output.split('\n'):
			if not line:
				continue
			parts = line.split('|', 4)
			if len(parts) == 5:
				commit_hash = parts[0]
				
				# Skip if we've already processed this commit (exists on multiple branches)
				if commit_hash in seen_hashes:
					continue
				seen_hashes.add(commit_hash)
				
				# Get line statistics for this commit
				line_stats = get_commit_line_stats(repo_path, commit_hash)
				
				# Get branch names for this commit (more reliable than fuzzy matching)
				# This helps match commits on feature branches like "feature/99-vendor-estimate-creation"
				branch_names = []
				try:
					branch_output = run_git_command(repo_path, 'branch', '--contains', commit_hash, '--all')
					if branch_output:
						# Extract branch names, remove * and remotes/ prefix
						for branch_line in branch_output.split('\n'):
							branch_line = branch_line.strip()
							if branch_line:
								# Remove * marker and remotes/origin/ prefix
								branch_name = branch_line.lstrip('* ').replace('remotes/origin/', '').replace('remotes/', '')
								if branch_name and branch_name != 'HEAD':
									branch_names.append(branch_name)
				except:
					pass  # If branch lookup fails, continue without it
				
				commits.append({
					'hash': commit_hash,
					'author': parts[1],
					'email': parts[2],
					'date': parts[3],
					'message': parts[4],
					'branches': branch_names,  # Add branch names for better matching
					'lines_added': line_stats['additions'],
					'lines_deleted': line_stats['deletions'],
					'lines_changed': line_stats['total_changed']
				})
	
	# Sort commits by date (oldest first) for consistent ordering
	commits.sort(key=lambda c: (c['date'], c['hash']))
	
	return commits

def estimate_hours_from_commits(commits: List[Dict]) -> float:
	"""
	Estimate hours based on lines changed (more objective than commit count)
	Rounds down towards impact made vs time spent
	"""
	if not commits:
		return 0.0
	
	total_hours = 0.0
	
	# Group commits by date to identify work sessions
	commits_by_date: Dict[str, List[Dict]] = {}
	for commit in commits:
		date = commit['date']
		if date not in commits_by_date:
			commits_by_date[date] = []
		commits_by_date[date].append(commit)
	
	# Estimate based on lines changed
	for date, day_commits in commits_by_date.items():
		total_lines = sum(c.get('lines_changed', 0) for c in day_commits)
		messages = [c.get('message', '').lower() for c in day_commits]
		
		# Check for merge commits (usually don't count as work)
		# Exclude merge pull requests and regular merge commits
		msg_lower = lambda c: c.get('message', '').lower()
		merge_commits = [
			c for c in day_commits 
			if ('merge pull request' in msg_lower(c) or 
				'merge pr' in msg_lower(c) or
				msg_lower(c).startswith('merge pull request') or
				msg_lower(c).startswith('merge pr') or
				('merge' in msg_lower(c) and 'branch' in msg_lower(c)))
		]
		non_merge_commits = [c for c in day_commits if c not in merge_commits]
		
		# Only count lines from non-merge commits
		non_merge_lines = sum(c.get('lines_changed', 0) for c in non_merge_commits)
		
		# Debug: show line counts per commit
		if len(day_commits) > 0:
			debug_info = []
			for c in non_merge_commits:
				lines = c.get('lines_changed', 0)
				if lines > 0:
					msg = c.get('message', '')[:50]
					debug_info.append(f"    {msg}: {lines} lines")
		
		# Base estimation: ~50-100 lines per hour (conservative, rounds down)
		# Adjust based on complexity
		has_major_feature = any(
			'feature' in msg or 'feat' in msg or 
			'oauth' in msg or 'setup' in msg or
			'refactor' in msg or 'architecture' in msg
			for msg in messages
		)
		
		has_docs = any('doc' in msg or 'readme' in msg or 'comment' in msg for msg in messages)
		
		# Lines per hour estimates (REALISTIC - developers write code much faster than this)
		# Higher number = fewer hours (more realistic estimate)
		# Typical developer: 200-500 lines/hour for regular work, 1000+ for boilerplate
		if has_major_feature:
			# Major features: more complex, but still ~200 lines/hour (realistic)
			lines_per_hour = 200
		elif has_docs:
			# Documentation: much faster, ~400 lines/hour
			lines_per_hour = 400
		else:
			# Regular code: ~250 lines/hour (realistic - developers are fast)
			lines_per_hour = 250
		
		# Calculate hours from lines
		if non_merge_lines > 0:
			day_hours = non_merge_lines / lines_per_hour
			# Minimum 0.25 hours if there's any code change
			day_hours = max(0.25, day_hours)
		else:
			# No code changes (maybe just merges or config)
			# Estimate minimal time: 0.25 hours
			day_hours = 0.25 if len(non_merge_commits) > 0 else 0.0
		
		# Cap removed - use calculated hours directly
		# The lines/hour rate (200-250) is already conservative enough
		# If you work 8 hours, you should bill 8 hours
		
		# Store debug info
		if hasattr(estimate_hours_from_commits, 'debug'):
			estimate_hours_from_commits.debug.append({
				'date': date,
				'lines': non_merge_lines,
				'hours': day_hours,
				'commits': len(non_merge_commits),
				'details': debug_info if 'debug_info' in locals() else []
			})
		
		total_hours += day_hours
	
	return round(total_hours, 2)

def estimate_hours_with_trello(
	commits: List[Dict],
	cards: List[Dict],
	card_commits: Dict[str, List[Dict]],
	config: Config,
	trello_client: Optional[TrelloClient] = None,
	since_date: str = None
) -> Dict:
	"""
	Enhanced hour estimation using both git commits and Trello estimates
	Cross-validates and provides more accurate estimates
	"""
	commit_based_hours = estimate_hours_from_commits(commits)
	
	# Calculate hours from Trello cards
	trello_total_estimated = 0.0
	trello_total_actual = 0.0
	matched_cards = []
	unmatched_cards = []
	unmatched_commits = list(commits)  # Start with all commits
	
	# Sort cards by ID for deterministic processing order
	for card in sorted(cards, key=lambda c: c.get('id', '')):
		card_id = card['id']
		card_estimated = card.get('estimatedHours')
		card_commits_list = card_commits.get(card_id, [])
		
		# Get hours from comments (for non-code work)
		comment_hours = 0.0
		try:
			# Get full card details to access comments
			from .trello_client import TrelloClient
			if hasattr(trello_client, 'extract_hours_from_comments'):
				actions_count = len(card.get('actions', []))
				comment_hours = trello_client.extract_hours_from_comments(card, since_date)
				if comment_hours > 0:
					card_name = sanitize_text(card.get('name', 'Unknown')[:40])
					print(f"  Card {card.get('idShort', '?')} ({card_name}): Found {comment_hours:.2f}h in comments ({actions_count} actions)")
		except Exception as e:
			print(f"  Warning: Failed to extract comment hours for card {card.get('idShort', '?')}: {e}")
		
		if card_commits_list:
			# Card has matching commits
			# Filter out ALL merge pull requests - they don't represent actual work time
			# Merge PRs are just merging work that's already been done and billed
			def is_merge_pr(commit):
				"""Check if a commit is a merge pull request"""
				msg = commit.get('message', '').lower()
				return ('merge pull request' in msg or 
						'merge pr' in msg or
						msg.startswith('merge pull request') or
						msg.startswith('merge pr') or
						('merge' in msg and 'pull' in msg) or
						('merge' in msg and 'pr #' in msg))
			
			def is_merge_conflict_resolution(commit):
				"""Check if a commit is a merge conflict resolution"""
				msg = commit.get('message', '').lower()
				return ('resolve merge conflict' in msg or
						'merge conflict' in msg or
						'resolved merge conflict' in msg or
						'fix merge conflict' in msg or
						'chore - resolve merge conflict' in msg)
			
			# Filter out merge PRs and merge conflict resolutions
			non_merge_pr_commits = [
				c for c in card_commits_list 
				if not is_merge_pr(c) and not is_merge_conflict_resolution(c)
			]
			
			# Debug: Show merge PRs and conflict resolutions that were filtered out
			merge_prs_filtered = [c for c in card_commits_list if is_merge_pr(c)]
			conflict_resolutions_filtered = [c for c in card_commits_list if is_merge_conflict_resolution(c)]
			if merge_prs_filtered or conflict_resolutions_filtered:
				card_num = extract_task_number(card) or '?'
				if merge_prs_filtered:
					print(f"  Card #{card_num}: Filtered out {len(merge_prs_filtered)} merge PR commits")
				if conflict_resolutions_filtered:
					total_conflict_lines = sum(c.get('lines_changed', 0) for c in conflict_resolutions_filtered)
					print(f"  Card #{card_num}: Filtered out {len(conflict_resolutions_filtered)} merge conflict resolution commits ({total_conflict_lines:,} lines)")
			
			commit_hours = estimate_hours_from_commits(non_merge_pr_commits)
			
			# Debug: Show commit breakdown for high commit hours
			if commit_hours > 10 and comment_hours > 0:
				card_num = extract_task_number(card) or '?'
				total_lines = sum(c.get('lines_changed', 0) for c in non_merge_pr_commits)
				print(f"  Card #{card_num}: {len(non_merge_pr_commits)} commits, {total_lines:,} lines = {commit_hours:.2f}h")
				print(f"    This will add {commit_hours * 0.1:.2f}h to your {comment_hours:.2f}h logged time")
			
			# Cross-check: Balance comment hours (manually logged) vs commit hours (calculated)
			# Use weighted average when both exist to balance manual logging with code-based estimates
			if comment_hours > 0:
				if commit_hours > 0:
					# Both exist - use weighted average (favor comment hours but include commit hours)
					# Weight: 90% comment hours, 10% commit hours
					# This balances manual logging with code-based validation while respecting logged time
					total_card_hours = (comment_hours * 0.9) + (commit_hours * 0.1)
				else:
					# Only comment hours exist
					total_card_hours = comment_hours
			else:
				# No comment hours, use commit-based estimation
				total_card_hours = commit_hours
			
			matched_cards.append({
				'card': card,
				'estimated_hours': card_estimated,
				'commits': non_merge_pr_commits,  # Store filtered commits (without merge PRs)
				'commit_based_hours': commit_hours,
				'comment_hours': comment_hours,
				'total_hours': total_card_hours
			})
			
			# Remove matched commits (match by hash for deterministic behavior)
			# Use the original card_commits_list (before filtering) to track all matched commits
			matched_hashes = {c.get('hash') for c in card_commits_list}
			unmatched_commits = [c for c in unmatched_commits if c.get('hash') not in matched_hashes]
			
			if card_estimated:
				trello_total_estimated += card_estimated
			
			# Use commit-based hours + comment hours
			trello_total_actual += total_card_hours
		elif comment_hours > 0:
			# Card has no matching commits but has comment hours - include it for billing
			# Comment hours indicate work was done (config, meetings, etc.)
			matched_cards.append({
				'card': card,
				'estimated_hours': card_estimated,
				'commits': [],
				'commit_based_hours': 0.0,
				'comment_hours': comment_hours,
				'total_hours': comment_hours
			})
			
			if card_estimated:
				trello_total_estimated += card_estimated
			
			# Use comment hours for billing
			trello_total_actual += comment_hours
		else:
			# Card has no matching commits and no comment hours
			if card_estimated:
				# Has estimate but no commits and no comment hours - needs attention
				unmatched_cards.append({
					'card': card,
					'estimated_hours': card_estimated,
					'comment_hours': 0.0,
					'needs_comment': True  # Flag for warning
				})
				trello_total_estimated += card_estimated
	
	# Calculate hours for unmatched commits (work not tracked in Trello)
	# Exclude merge commits - they don't represent actual work
	unmatched_non_merge = [c for c in unmatched_commits if 'merge' not in c.get('message', '').lower()]
	unmatched_hours = estimate_hours_from_commits(unmatched_non_merge)
	
	# Final estimate: combine Trello estimates with unmatched commit hours
	# Weight Trello estimates higher since they're more intentional
	final_estimated_hours = trello_total_actual + unmatched_hours
	
	# Calculate accuracy metrics
	accuracy_metrics = {
		'cards_with_estimates': len([c for c in cards if c.get('estimatedHours')]),
		'cards_matched': len(matched_cards),
		'cards_unmatched': len(unmatched_cards),
		'commits_matched': len(commits) - len(unmatched_commits),
		'commits_unmatched': len(unmatched_commits),
		'trello_estimated_total': trello_total_estimated,
		'commit_based_total': commit_based_hours,
		'final_estimated': final_estimated_hours
	}
	
	return {
		'estimated_hours': round(final_estimated_hours, 2),
		'commit_based_hours': commit_based_hours,
		'trello_based_hours': round(trello_total_actual, 2),
		'unmatched_hours': round(unmatched_hours, 2),
		'matched_cards': matched_cards,
		'unmatched_cards': unmatched_cards,
		'unmatched_commits': unmatched_commits,
		'accuracy_metrics': accuracy_metrics
	}

def get_commit_stats(repo_path: str, since_date: str, author: str = None, 
					trello_client: Optional[TrelloClient] = None,
					trello_board_id: Optional[str] = None,
					config: Optional[Config] = None) -> Dict:
	"""Get comprehensive commit statistics with optional Trello integration"""
	commits = get_commits_since(repo_path, since_date, author)
	
	if not commits:
		return {
			'commit_count': 0,
			'estimated_hours': 0.0,
			'estimated_amount': 0.0,
			'commits': [],
			'date_range': {
				'start': None,
				'end': None
			},
			'trello_enabled': False
		}
	
	# If Trello is available, use enhanced estimation
	if trello_client and trello_board_id:
		try:
			# Get all cards with basic info (fast - no API calls for details yet)
			cards = trello_client.get_cards_with_estimates(trello_board_id, since_date=None)
			
			# Filter to only WIP and Done cards
			lists = trello_client.get_board_lists(trello_board_id)
			wip_done_lists = {list_id: name for list_id, name in lists.items() 
							  if any(keyword in name.upper() for keyword in ['WIP', 'DONE', 'COMPLETE', 'FINISHED'])}
			
			if not wip_done_lists:
				print("WARNING: No 'WIP' or 'Done' lists found. Using all cards.")
				filtered_cards = cards
			else:
				filtered_cards = [card for card in cards if card.get('idList') in wip_done_lists]
				print(f"Filtered cards: {len(filtered_cards)} in WIP/Done lists (out of {len(cards)} total)")
				if wip_done_lists:
					sanitized_list_names = [sanitize_text(name) for name in wip_done_lists.values()]
					print(f"  Lists included: {', '.join(sanitized_list_names)}")
			
			# Filter by member ID if configured (before matching commits)
			if config and config.trello_member_id:
				member_id = config.trello_member_id
				print(f"\nFiltering cards by member ID: {member_id[:8]}...")
				# Get basic member info for cards (more efficient than full details)
				member_filtered_cards = []
				for card in filtered_cards:
					try:
						# Get just the members for this card (lighter API call)
						members = trello_client._request(f"cards/{card['id']}/members")
						card_member_ids = [m.get('id') for m in members]
						if member_id in card_member_ids:
							member_filtered_cards.append(card)
					except:
						continue
				print(f"Filtered to {len(member_filtered_cards)} cards assigned to you (out of {len(filtered_cards)} in WIP/Done)")
				
				# If member filtering results in 0 cards but we have commits that reference cards,
				# skip the member filter to allow matching (cards might not be assigned but commits reference them)
				if len(member_filtered_cards) == 0 and len(commits) > 0:
					print(f"  Warning: No cards assigned to you, but {len(commits)} commits found.")
					print(f"     Skipping member filter to allow card matching by commit references.")
					print(f"     (Cards may not be assigned in Trello but commits reference them)")
					# Keep using filtered_cards (before member filtering) so matching can proceed
				else:
					filtered_cards = member_filtered_cards
			
			# Match commits to cards first (using basic card info)
			print(f"\nMatching {len(commits)} commits to {len(filtered_cards)} cards...")
			# Pass author filter to exclude commits from main (by other authors) when matched by branch name
			card_commits = trello_client.match_commits_to_cards(commits, filtered_cards, expected_author=author)
			print(f"Match results: {len(card_commits)} cards have matching commits")
			
			# Fetch full details (comments) for ALL cards in WIP/Done lists
			# This ensures we can check for comment hours even on cards without matching commits
			all_card_ids = [card['id'] for card in filtered_cards]
			if all_card_ids:
				print(f"Fetching full details (including comments) for {len(all_card_ids)} cards...")
				card_details_map = trello_client.get_card_details_for_matched(all_card_ids)
				# Merge full details into cards
				for card in filtered_cards:
					if card['id'] in card_details_map:
						details = card_details_map[card['id']]
						card['actions'] = details.get('actions', [])
						# Preserve idShort if needed
						if 'idShort' not in details and 'idShort' in card:
							details['idShort'] = card['idShort']
						# Update card with additional fields
						card.update({k: v for k, v in details.items() if k not in ['actions']})
						card['actions'] = details.get('actions', [])
			
			estimation = estimate_hours_with_trello(commits, filtered_cards, card_commits, config, trello_client, since_date)
			
			return {
				'commit_count': len(commits),
				'estimated_hours': estimation['estimated_hours'],
				'estimated_amount': round(estimation['estimated_hours'] * config.hourly_rate, 2),
				'commits': commits,
				'date_range': {
					'start': commits[-1]['date'] if commits else None,
					'end': commits[0]['date'] if commits else None
				},
				'trello_enabled': True,
				'estimation_details': estimation,
				'cards': cards
			}
		except Exception as e:
			print(f"Warning: Trello integration failed: {e}", file=sys.stderr)
			print("Falling back to commit-based estimation only.", file=sys.stderr)
	
	# Fallback to commit-based estimation only
	estimated_hours = estimate_hours_from_commits(commits)
	hourly_rate = config.hourly_rate if config else 80.0
	
	return {
		'commit_count': len(commits),
		'estimated_hours': estimated_hours,
		'estimated_amount': round(estimated_hours * hourly_rate, 2),
		'commits': commits,
		'date_range': {
			'start': commits[-1]['date'] if commits else None,
			'end': commits[0]['date'] if commits else None
		},
		'trello_enabled': False
	}

def extract_card_numbers_from_merge_pr(message: str) -> List[str]:
	"""
	Extract card numbers from a merge pull request message.
	
	Merge PR format: "Merge pull request #24 from MadiCat206/feature/18-phase-1-in-platform-"
	This function extracts "18" from the branch name "feature/18-phase-1-in-platform-"
	
	Returns:
		List of card numbers found in the branch name
	"""
	card_numbers = []
	msg_lower = message.lower()
	
	# Check if this is a merge pull request
	if 'merge pull request' in msg_lower or 'merge pr' in msg_lower:
		# Extract branch name from merge PR message
		# Pattern: "from USERNAME/BRANCH_NAME" or "from BRANCH_NAME"
		branch_match = re.search(r'from\s+[\w-]+/([^\s]+)', msg_lower)
		if not branch_match:
			# Try without username: "from feature/18-..."
			branch_match = re.search(r'from\s+([^\s]+)', msg_lower)
		
		if branch_match:
			branch_name = branch_match.group(1)
			# Extract card numbers from branch name (e.g., "feature/18-phase-1" -> "18")
			# Look for patterns like: /18-, -18-, /18/, etc.
			card_num_matches = re.findall(r'[/-](\d+)[/-]', branch_name)
			card_numbers.extend(card_num_matches)
			
			# Also check if branch starts with a number
			leading_num = re.match(r'^(\d+)', branch_name)
			if leading_num:
				card_numbers.append(leading_num.group(1))
	
	return card_numbers

def extract_task_number(card: Dict) -> Optional[str]:
	"""Extract task number from Trello card (uses card short ID)"""
	# Use the card's short ID (the number shown in Trello URLs)
	short_id = card.get('idShort')
	if short_id:
		return str(short_id)
	# Fallback: look for #33 pattern in card name
	name = card.get('name', '')
	match = re.search(r'#(\d+)', name)
	if match:
		return match.group(1)
	return None

def determine_category(card: Dict, commits: List[Dict]) -> str:
	"""
	Determine invoice category (FEAT/MAINT, FIX/MAINT, MAINT, etc.)
	based on card labels, name, and commit messages
	"""
	name_lower = card.get('name', '').lower()
	desc_lower = card.get('desc', '').lower()
	
	# Check labels
	labels = [label.get('name', '').lower() for label in card.get('labels', [])]
	
	# Check commit messages
	commit_messages = ' '.join([c.get('message', '').lower() for c in commits])
	all_text = f"{name_lower} {desc_lower} {commit_messages}"
	
	# Determine category
	has_feat = any(x in all_text for x in ['feat', 'feature', 'new', 'add', 'implement'])
	has_fix = any(x in all_text for x in ['fix', 'bug', 'error', 'issue', 'resolve', 'patch'])
	has_maint = any(x in all_text for x in ['maint', 'maintenance', 'cleanup', 'refactor', 'update'])
	
	# Check labels for category hints
	if any('feat' in l or 'feature' in l for l in labels):
		has_feat = True
	if any('fix' in l or 'bug' in l for l in labels):
		has_fix = True
	if any('maint' in l or 'maintenance' in l for l in labels):
		has_maint = True
	
	# Build category string
	category_parts = []
	if has_feat:
		category_parts.append('FEAT')
	if has_fix:
		category_parts.append('FIX')
	if has_maint:
		category_parts.append('MAINT')
	
	if category_parts:
		return '/'.join(category_parts)
	return 'MAINT'  # Default

def generate_invoice_line_items(stats: Dict, config: Config) -> List[Dict]:
	"""
	Generate invoice line items from tracking statistics
	
	Returns:
		List of dicts with keys: task_number, description, category, amount
	"""
	line_items = []
	
	if stats.get('trello_enabled') and 'estimation_details' in stats:
		# Use Trello-matched cards
		details = stats['estimation_details']
		matched_cards = details.get('matched_cards', [])
		
		print(f"\nProcessing {len(matched_cards)} matched cards for invoice...")
		excluded_count = 0
		
		for match in matched_cards:
			card = match['card']
			task_num = extract_task_number(card) or 'N/A'
			card_name = sanitize_text(card.get('name', 'Unknown Task'))
			
			# Check if card is manually excluded
			if task_num in config.excluded_cards:
				print(f"WARNING: Excluding card #{task_num} ({card_name[:40]}) - manually excluded in config")
				excluded_count += 1
				continue
			
			# Check if this is a weak fuzzy match that should be excluded
			commits = match.get('commits', [])
			fuzzy_commits = [c for c in commits if c.get('_match_type') == 'fuzzy']
			explicit_commits = [c for c in commits if c.get('_match_type') == 'explicit']
			
			# Don't exclude fuzzy matches - if it matched, bill it
			# The matching logic is conservative enough, we should trust it
			
			# Use total hours (commit-based + comment hours) for actual work done
			hours = match.get('total_hours', match.get('commit_based_hours', 0))
			commit_hours_debug = match.get('commit_based_hours', 0)
			comment_hours_debug = match.get('comment_hours', 0)
			amount = round(hours * config.hourly_rate, 2)
			
			# Debug output for hours calculation
			print(f"Card #{task_num}: commit_hours={commit_hours_debug:.2f}h, comment_hours={comment_hours_debug:.2f}h, total={hours:.2f}h, amount=${amount:.2f}")
			
			# Show which commits matched this card
			if commits:
				explicit_count = len([c for c in commits if c.get('_match_type') == 'explicit'])
				fuzzy_count = len([c for c in commits if c.get('_match_type') == 'fuzzy'])
				print(f"  Matched {len(commits)} commits ({explicit_count} explicit, {fuzzy_count} fuzzy):")
				for commit in commits[:3]:  # Show first 3 commits
					match_type = commit.get('_match_type', 'unknown')
					msg = sanitize_text(commit.get('message', '')[:60])
					lines = commit.get('lines_changed', 0)
					print(f"    [{match_type}] {msg} ({lines} lines)")
				if len(commits) > 3:
					print(f"    ... and {len(commits) - 3} more commits")
			
			# Skip line items with $0.00 (no work done in this period)
			if amount == 0:
				print(f"INFO: Skipping card #{task_num} ({card_name[:40]}) - $0.00 (no hours)")
				excluded_count += 1
				continue
			
			# Get category
			category = determine_category(card, commits)
			
			# Build description with per-card breakdown
			commit_hours = match.get('commit_based_hours', 0)
			comment_hours = match.get('comment_hours', 0)
			
			# Calculate lines of code for this card
			total_lines = sum(c.get('lines_changed', 0) for c in commits)
			non_merge_commits = [c for c in commits if 'merge' not in c.get('message', '').lower()]
			non_merge_lines = sum(c.get('lines_changed', 0) for c in non_merge_commits)
			
			# Build description with breakdown
			desc_parts = []
			# Clean up card name - remove trailing task identifiers in parentheses
			# Increase limit to 60 chars to avoid cutting off important words
			card_name_clean = card_name[:60]
			# Remove trailing patterns like (T3, (T3 -, or (T3) that would create double parentheses
			# This handles cases where card name ends with (T3 and then " - " joins it with breakdown
			card_name_clean = re.sub(r'\s*\([Tt]\d+\s*-?\s*$', '', card_name_clean)
			card_name_clean = re.sub(r'\s*\([Tt]\d+\)\s*$', '', card_name_clean)
			
			if commits:
				# Card has commits - show full breakdown
				desc_parts.append(card_name_clean)
				# Add breakdown: commits, lines, hours
				breakdown = f"({len(non_merge_commits)} commits, {non_merge_lines:,} lines"
				if comment_hours > 0:
					breakdown += f", {comment_hours}h comments"
				breakdown += ")"
				desc_parts.append(breakdown)
				description = " - ".join(desc_parts)
			elif comment_hours > 0:
				# No commits, but has comment hours (config work, meetings, etc.)
				# Add context about why no commits (config, meetings, planning, etc.)
				description = f"{card_name_clean} - ({comment_hours}h comments, no commits)"
			else:
				# No commits and no comment hours (shouldn't happen, but handle gracefully)
				description = card_name_clean
			
			line_items.append({
				'task_number': task_num,
				'description': description,
				'category': category,
				'amount': amount
			})
		
		# Don't create #N/A line items - unmatched commits are not billed
		# This ensures all invoice items are tied to Trello cards for stakeholder clarity
		
		print(f"Invoice line items: {len(line_items)} created, {excluded_count} excluded")
		
		# Sort line items by task number for consistent invoice ordering
		def sort_key(item):
			task_num = item.get('task_number', '')
			try:
				return int(task_num)  # Sort by numeric value
			except (ValueError, TypeError):
				return 999999  # Non-numeric tasks go last
		
		line_items.sort(key=sort_key)
	else:
		# No Trello - create a single line item from all commits
		hours = stats.get('estimated_hours', 0)
		if hours > 0:
			line_items.append({
				'task_number': 'ALL',
				'description': f"Web development work ({stats.get('commit_count', 0)} commits)",
				'category': 'FEAT/MAINT',
				'amount': stats.get('estimated_amount', 0)
			})
	
	return line_items

def print_report(stats: Dict, author: str = None, config: Config = None):
	"""Print a formatted billing report with Trello integration details"""
	print("\n" + "="*70)
	print("WORK TIME TRACKING REPORT")
	print("="*70)
	
	if author:
		print(f"Author: {author}")
	
	if stats.get('date_range', {}).get('start'):
		print(f"Date Range: {stats['date_range']['start']} to {stats['date_range']['end']}")
	elif stats.get('date_range', {}).get('start') is None and stats['commit_count'] == 0:
		print("No commits found in the specified date range.")
	
	hourly_rate = config.hourly_rate if config else 80.0
	
	# Calculate total lines changed for transparency
	total_lines = sum(c.get('lines_changed', 0) for c in stats.get('commits', []))
	non_merge_commits = [c for c in stats.get('commits', []) if 'merge' not in c.get('message', '').lower()]
	non_merge_lines = sum(c.get('lines_changed', 0) for c in non_merge_commits)
	
	print(f"\nCommits: {stats['commit_count']} (non-merge: {len(non_merge_commits)})")
	print(f"Lines Changed: {non_merge_lines:,} (total: {total_lines:,})")
	print(f"Estimated Hours: {stats['estimated_hours']}")
	print(f"Hourly Rate: ${hourly_rate:.2f}")
	print(f"Estimated Amount: ${stats['estimated_amount']:.2f}")
	
	# Show breakdown by date
	if stats.get('commits'):
		print("\n" + "-"*70)
		print("DAILY BREAKDOWN:")
		print("-"*70)
		commits_by_date = {}
		for commit in stats.get('commits', []):
			date = commit['date']
			if date not in commits_by_date:
				commits_by_date[date] = []
			commits_by_date[date].append(commit)
		
		for date in sorted(commits_by_date.keys()):
			day_commits = commits_by_date[date]
			non_merge = [c for c in day_commits if 'merge' not in c.get('message', '').lower()]
			lines = sum(c.get('lines_changed', 0) for c in non_merge)
			hours = estimate_hours_from_commits(non_merge)
			print(f"  {date}: {len(non_merge)} commits, {lines:,} lines -> {hours}h")
			# Show top commits by line count
			if non_merge:
				top_commits = sorted(non_merge, key=lambda x: x.get('lines_changed', 0), reverse=True)[:3]
				for c in top_commits:
					lines_c = c.get('lines_changed', 0)
					if lines_c > 0:
						msg = c.get('message', '')[:60]
						print(f"    - {msg}: {lines_c:,} lines")
	
	# Show Trello integration details if enabled
	if stats.get('trello_enabled') and 'estimation_details' in stats:
		details = stats['estimation_details']
		metrics = details['accuracy_metrics']
		
		print("\n" + "-"*70)
		print("TRELLO INTEGRATION ANALYSIS")
		print("-"*70)
		print(f"Cards with Estimates: {metrics['cards_with_estimates']}")
		print(f"Cards Matched to Commits: {metrics['cards_matched']}")
		print(f"Cards Unmatched: {metrics['cards_unmatched']}")
		print(f"Commits Matched to Cards: {metrics['commits_matched']}")
		print(f"Commits Unmatched: {metrics['commits_unmatched']}")
		print(f"\nBreakdown:")
		print(f"  Trello-based Hours: {details['trello_based_hours']}")
		print(f"  Unmatched Commit Hours: {details['unmatched_hours']}")
		print(f"  Commit-only Estimate: {details['commit_based_hours']}")
		
		# Show matched cards
		if details['matched_cards']:
			print("\n" + "-"*70)
			print("MATCHED TRELLO CARDS:")
			print("-"*70)
			for match in details['matched_cards'][:10]:
				card = match['card']
				est = match['estimated_hours']
				commit_hours = match['commit_based_hours']
				comment_hours = match.get('comment_hours', 0.0)
				total_hours = match.get('total_hours', commit_hours)
				status = "[OK]" if est and abs(est - total_hours) < 1.0 else "[~]"
				card_name = sanitize_text(card['name'][:50])
				print(f"  {status} {card_name}")
				if est:
					if comment_hours > 0:
						print(f"      Est: {est}h | Actual: {total_hours}h (commits: {commit_hours}h + comments: {comment_hours}h) | Commits: {len(match['commits'])}")
					else:
						print(f"      Est: {est}h | Actual: {total_hours}h | Commits: {len(match['commits'])}")
				else:
					if comment_hours > 0:
						print(f"      Actual: {total_hours}h (commits: {commit_hours}h + comments: {comment_hours}h) | Commits: {len(match['commits'])}")
					else:
						print(f"      Actual: {total_hours}h | Commits: {len(match['commits'])}")
		
		# Show unmatched cards (estimated work not done)
		if details['unmatched_cards']:
			print("\n" + "-"*70)
			print(f"UNMATCHED CARDS (Estimated but no commits): {len(details['unmatched_cards'])}")
			print("-"*70)
			for match in details['unmatched_cards'][:5]:
				card = match['card']
				est = match['estimated_hours']
				card_name = sanitize_text(card['name'][:50])
				print(f"  [WARNING] {card_name} - Est: {est}h")
	
	# Show recent commits
	if stats['commits']:
		print("\n" + "-"*70)
		print("Recent Commits:")
		print("-"*70)
		for commit in stats['commits'][:10]:  # Show last 10
			print(f"  {commit['date']} - {commit['message'][:60]}")
		if len(stats['commits']) > 10:
			print(f"  ... and {len(stats['commits']) - 10} more")

def main():
	"""Main entry point"""
	import argparse
	
	parser = argparse.ArgumentParser(
		description='Track work time from git commits and Trello tasks',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Examples:
  python track_work.py ../myproject 2024-11-10
  python track_work.py ../myproject 2024-11-10 "john|John"
  python track_work.py ../myproject 2024-11-10 --invoice --invoice-num 2
  python track_work.py ../myproject 2024-11-10 --invoice --invoice-date 11/20/24
		"""
	)
	
	parser.add_argument('repo_path', help='Path to git repository')
	parser.add_argument('since_date', nargs='?', default='2024-11-01',
					   help='Start date for analysis (YYYY-MM-DD, default: 2024-11-01)')
	parser.add_argument('author', nargs='?', default=None,
					   help='Filter commits by author (supports regex)')
	parser.add_argument('trello_board_id', nargs='?', default=None,
					   help='Trello board ID (or set TRELLO_BOARD_ID env var)')
	parser.add_argument('--invoice', action='store_true',
					   help='Generate invoice PDF')
	parser.add_argument('--invoice-num', type=int, default=1,
					   help='Invoice number (default: 1)')
	parser.add_argument('--invoice-date', type=str, default=None,
					   help='Invoice date (MM/DD/YY format, defaults to today)')
	parser.add_argument('--invoice-output', type=str, default='invoices',
					   help='Directory to save invoice PDF (default: invoices/)')
	parser.add_argument('--skip-warnings', action='store_true',
					   help='Skip warnings about cards missing hour comments')
	parser.add_argument('--breakdown', action='store_true',
					   help='Include detailed work breakdown page in invoice')
	
	args = parser.parse_args()
	
	repo_path = args.repo_path
	since_date = args.since_date
	author = args.author
	trello_board_id = args.trello_board_id
	
	# Load configuration
	config = Config()
	
	# Validate repo path
	if not Path(repo_path).joinpath('.git').exists():
		print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
		sys.exit(1)
	
	# Initialize Trello client if credentials are available
	trello_client = None
	if config.has_trello_credentials():
		trello_board_id = trello_board_id or config.trello_board_id
		if trello_board_id:
			try:
				trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
				print(f"Trello integration enabled (Board: {trello_board_id[:8]}...)")
			except Exception as e:
				print(f"Warning: Failed to initialize Trello client: {e}", file=sys.stderr)
		else:
			print("Warning: Trello credentials found but no board ID specified.", file=sys.stderr)
			print("Set TRELLO_BOARD_ID or pass as 4th argument.", file=sys.stderr)
	else:
		print("INFO: Trello integration not configured. Using commit-based estimation only.")
		print("  Set TRELLO_API_KEY and TRELLO_API_TOKEN to enable Trello integration.")
	
	stats = get_commit_stats(repo_path, since_date, author, trello_client, trello_board_id, config)
	print_report(stats, author, config)
	
	# Generate invoice if requested
	if args.invoice:
		print("\n" + "="*70)
		print("GENERATING INVOICE...")
		print("="*70)
		
		# Check for cards with estimates but no hours tracked
		if stats.get('trello_enabled') and 'estimation_details' in stats:
			details = stats['estimation_details']
			unmatched_cards = details.get('unmatched_cards', [])
			cards_needing_comments = [c for c in unmatched_cards if c.get('needs_comment')]
			
			if cards_needing_comments and not args.skip_warnings:
				print("\n" + "!"*70)
				print("WARNING: Cards with estimates but no hours tracked!")
				print("!"*70)
				print("\nThe following cards have estimates but no commits or comment hours:")
				print("Please add hour comments to these cards (e.g., '1.5h config work')")
				print("or remove the estimate if work wasn't done.\n")
				
				for card_info in cards_needing_comments:
					card = card_info['card']
					card_name = sanitize_text(card.get('name', 'Unknown')[:60])
					est = card_info.get('estimated_hours', 0)
					card_id = card.get('id', '')
					card_url = f"https://trello.com/c/{card_id}"
					print(f"  - {card_name}")
					print(f"    Est: {est}h | URL: {card_url}")
				
				print("\n" + "-"*70)
				print("Invoice generation STOPPED.")
				print("Add comments with hours (e.g., '1.5h') to the cards above,")
				print("or run with --skip-warnings to proceed anyway.")
				print("-"*70)
				sys.exit(1)
		
		line_items = generate_invoice_line_items(stats, config)
		
		if not line_items:
			print("Error: No line items to invoice. No work found or no matched Trello cards.")
			sys.exit(1)
		
		# Print calculation summary for verification
		print("\n" + "-"*70)
		print("INVOICE CALCULATION SUMMARY")
		print("-"*70)
		total_amount = sum(item['amount'] for item in line_items)
		
		# Calculate billed hours from line items
		billed_hours = total_amount / config.hourly_rate
		
		print(f"Line items: {len(line_items)}")
		print(f"Billed hours: {billed_hours:.2f}h")
		print(f"Hourly rate: ${config.hourly_rate:.2f}")
		print(f"Total amount: ${total_amount:,.2f}")
		
		if stats.get('trello_enabled') and 'estimation_details' in stats:
			details = stats['estimation_details']
			matched_cards_with_hours = [m for m in details.get('matched_cards', []) if m.get('total_hours', 0) > 0]
			matched_hours = sum(m.get('total_hours', 0) for m in matched_cards_with_hours)
			unmatched_commits = details.get('unmatched_commits', [])
			unmatched_hours = details.get('unmatched_hours', 0)
			total_work_hours = details.get('estimated_hours', 0)
			
			print(f"\nWork Breakdown:")
			print(f"  Trello-matched cards: {len(matched_cards_with_hours)} ({matched_hours:.2f}h)")
			print(f"  Unmatched commits: {len(unmatched_commits)} ({unmatched_hours:.2f}h) - NOT BILLED")
			print(f"  Total work done: {total_work_hours:.2f}h")
			print(f"\n  Billed: {billed_hours:.2f}h (${total_amount:,.2f})")
			print(f"  Not billed: {total_work_hours - billed_hours:.2f}h (unmatched commits excluded)")
		print("-"*70)
		
		# Convert date format if needed
		invoice_date = args.invoice_date
		if invoice_date and '-' in invoice_date:
			# Convert YYYY-MM-DD to MM/DD/YY
			try:
				dt = datetime.strptime(invoice_date, '%Y-%m-%d')
				invoice_date = dt.strftime('%m/%d/%y')
			except:
				pass
		
		try:
			# Create invoice generator from config
			from .invoice_generator import InvoiceGenerator
			generator = InvoiceGenerator(
				sender_name=config.sender_name,
				sender_address=config.sender_address,
				sender_phone=config.sender_phone,
				sender_email=config.sender_email,
				recipient_name=config.recipient_name,
				invoice_prefix=config.invoice_prefix
			)
			
			output_path = create_invoice_from_tracking_data(
				stats=stats,
				line_items=line_items,
				invoice_date=invoice_date,
				invoice_number=args.invoice_num,
				output_dir=args.invoice_output,
				generator=generator,
				include_breakdown=args.breakdown
			)
			print(f"\nInvoice generated: {output_path}")
			print(f"  Invoice #: {generator.generate_invoice_number(args.invoice_num)}")
			print(f"  Total: ${sum(item['amount'] for item in line_items):,.2f}")
		except Exception as e:
			print(f"\nError generating invoice: {e}", file=sys.stderr)
			import traceback
			traceback.print_exc()
			sys.exit(1)

if __name__ == '__main__':
	main()
