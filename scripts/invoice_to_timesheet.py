#!/usr/bin/env python3
"""
Convert invoice line items to Google Sheets timesheet format

This script uses the EXACT same workflow as the invoice generator to ensure
the timesheet matches the invoice exactly (same source of truth).

Workflow:
1. Calls get_commit_stats() - same as invoice generator
2. Calls generate_invoice_line_items() - same function as invoice generator
3. Formats the line items for Google Sheets

This ensures the timesheet rows match the invoice line items exactly.
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.track_work import get_commit_stats, generate_invoice_line_items, extract_task_number
from src.config import Config
from src.trello_client import TrelloClient

def extract_comment_dates(card: Dict) -> List[str]:
    """Extract dates from Trello comments that have hours logged"""
    try:
        from dateutil import parser as date_parser
    except ImportError:
        return []
    
    import re
    dates = []
    
    hour_patterns = [
        r'(?:^|[^\d@])(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
        r'spent\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
        r'worked\s+(\d+\.?\d*)\s*h(?:ours?|rs?)(?:\s|$|[^\d])',
    ]
    
    minute_patterns = [
        r'(?:^|[^\d@])(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
        r'spent\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
        r'worked\s+(\d+\.?\d*)\s*(?:min|mins|minutes?)(?:\s|$|[^\d])',
    ]
    
    actions = card.get('actions', [])
    comments = [a for a in actions if a.get('type') == 'commentCard']
    
    for comment in comments:
        comment_date_str = comment.get('date', '')
        if not comment_date_str or not date_parser:
            continue
        
        try:
            comment_dt = date_parser.parse(comment_date_str)
            comment_date = comment_dt.date().strftime('%Y-%m-%d')
        except:
            continue
        
        # Check if comment has hours
        text = comment.get('data', {}).get('text', '')
        has_hours = False
        for pattern in hour_patterns + minute_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                has_hours = True
                break
        
        if has_hours:
            dates.append(comment_date)
    
    return dates

def format_line_items_for_timesheet(line_items: List[Dict],
                                     stats: Dict,
                                     since_date: str = None,
                                     board: str = "ACME Development",
                                     project: str = "ACME") -> List[List[str]]:
    """
    Format invoice line items for Google Sheets timesheet with actual work dates
    
    Returns a list of rows, where each row is:
    [Date, Board, Card Title, Project, Task/Notes]
    """
    rows = []
    
    # Get matched cards from stats to extract dates
    matched_cards_map = {}
    if stats.get('trello_enabled') and 'estimation_details' in stats:
        details = stats['estimation_details']
        matched_cards = details.get('matched_cards', [])
        for match in matched_cards:
            card = match['card']
            task_num = extract_task_number(card) or 'N/A'
            matched_cards_map[task_num] = match
    
    for item in line_items:
        task_num = item.get('task_number', 'N/A')
        description = item.get('description', '')
        
        # Format task notes: task number + description
        task_notes = f"#{task_num} - {description}" if task_num != 'N/A' else description
        
        # Get actual work dates for this card
        work_date = None
        if task_num in matched_cards_map:
            match = matched_cards_map[task_num]
            commits = match.get('commits', [])
            card = match['card']
            
            # Get dates from commits (filter out merge commits)
            commit_dates = []
            msg_lower = lambda c: c.get('message', '').lower()
            non_merge_commits = [
                c for c in commits 
                if not ('merge pull request' in msg_lower(c) or 
                       'merge pr' in msg_lower(c) or
                       msg_lower(c).startswith('merge pull request') or
                       msg_lower(c).startswith('merge pr') or
                       ('merge' in msg_lower(c) and 'branch' in msg_lower(c)))
            ]
            for commit in non_merge_commits:
                date = commit.get('date', '')
                if date:
                    # Only include dates on or after since_date
                    if since_date and date < since_date:
                        continue
                    commit_dates.append(date)
            
            # Get dates from comments (already filtered by since_date in extract_comment_dates)
            comment_dates = extract_comment_dates(card)
            # Filter comment dates by since_date if provided
            if since_date:
                comment_dates = [d for d in comment_dates if d >= since_date]
            
            # Use earliest date from commits or comments (within the date range)
            all_dates = commit_dates + comment_dates
            if all_dates:
                work_date = min(all_dates)  # Use earliest work date within range
        
        # Fallback to a default date if no dates found (shouldn't happen for billed items)
        if not work_date:
            work_date = stats.get('date_range', {}).get('start') or datetime.now().strftime('%Y-%m-%d')
        
        row = [
            work_date,                   # Date (actual work date)
            board,                       # Board
            board,                       # Card Title (free text)
            project,                     # Project
            task_notes                   # Task/Notes
        ]
        rows.append(row)
    
    # Sort by date (ascending - oldest first)
    rows.sort(key=lambda r: r[0])
    
    return rows

def output_tsv_to_stdout(rows: List[List[str]]):
    """Output rows as TSV (tab-separated) - exact format that works in Google Sheets"""
    # Output exactly like test_paste.txt - simple tab-separated, one row per line
    for row in rows:
        # Clean cells: remove newlines, carriage returns, and any tabs within cells
        clean_row = []
        for cell in row:
            cell_str = str(cell).replace('\n', ' ').replace('\r', '').replace('\t', ' ')
            clean_row.append(cell_str)
        # Join with tab character (same as test_paste.txt)
        print('\t'.join(clean_row))

def main():
    """Main entry point"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        description='Convert invoice line items to Google Sheets timesheet format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate timesheet from invoice data (uses same flags as invoice generator)
  python invoice_to_timesheet.py ../myproject 2025-11-01
  
  # With author filter
  python invoice_to_timesheet.py ../myproject 2025-11-01 "john|John"
  
  # Use specific invoice date
  python invoice_to_timesheet.py ../myproject 2025-11-01 --invoice-date "12/04/2025"
  
  # Custom board and project names
  python invoice_to_timesheet.py ../myproject 2025-11-01 --board "My Board" --project "My Project"
        """
    )
    
    parser.add_argument('repo_path', help='Path to git repository')
    parser.add_argument('since_date', nargs='?', default='2025-11-01',
                       help='Start date for analysis (YYYY-MM-DD, default: 2025-11-01)')
    parser.add_argument('author', nargs='?', default=None,
                       help='Filter commits by author (supports regex)')
    parser.add_argument('trello_board_id', nargs='?', default=None,
                       help='Trello board ID (or set TRELLO_BOARD_ID env var)')
    parser.add_argument('--invoice-date', type=str, default=None,
                       help='Date to use for timesheet (MM/DD/YYYY format, defaults to today)')
    parser.add_argument('--board', type=str, default=None,
                       help='Board name for timesheet (default: from .env or "ACME Development")')
    parser.add_argument('--project', type=str, default=None,
                       help='Project name for timesheet (default: from .env or "ACME")')
    parser.add_argument('--csv', type=str, default=None,
                       help='Output as CSV file instead of TSV to stdout')
    parser.add_argument('--tsv', type=str, default=None,
                       help='Output as TSV file (tab-separated) - open file and copy/paste from there')
    
    args = parser.parse_args()
    
    # Validate repo path
    if not Path(args.repo_path).joinpath('.git').exists():
        print(f"Error: {args.repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
    
    # Load configuration (reads from .env file automatically)
    config = Config()
    
    # Use .env values for board/project if not specified on command line
    board_name = args.board or os.getenv('TIMESHEET_BOARD', 'ACME Development')
    project_name = args.project or os.getenv('TIMESHEET_PROJECT', 'ACME')
    
    # Get Trello board ID (command line arg > .env > config default)
    trello_board_id = args.trello_board_id or config.trello_board_id
    
    # Initialize Trello client if API key/token are available
    trello_client = None
    if config.trello_api_key and config.trello_api_token:
        try:
            trello_client = TrelloClient(config.trello_api_key, config.trello_api_token)
        except Exception as e:
            print(f"Warning: Failed to initialize Trello client: {e}", file=sys.stderr)
            print("Continuing without Trello integration...", file=sys.stderr)
    
    if not trello_client or not trello_board_id:
        print("Error: Trello integration required.", file=sys.stderr)
        print("Set TRELLO_API_KEY, TRELLO_API_TOKEN, and TRELLO_BOARD_ID in .env file or environment.", file=sys.stderr)
        sys.exit(1)
    
    # IMPORTANT: Use the EXACT same workflow as the invoice generator
    # This ensures the timesheet matches the invoice exactly (same source of truth)
    
    # Step 1: Get commit statistics (SAME as invoice generator)
    # NOTE: This may take a while because it fetches full details for ALL cards
    print(f"Analyzing commits since {args.since_date}...", file=sys.stderr)
    print("This may take a few minutes if you have many Trello cards...", file=sys.stderr)
    stats = get_commit_stats(
        repo_path=args.repo_path,
        since_date=args.since_date,
        author=args.author,
        trello_client=trello_client,
        trello_board_id=trello_board_id,
        config=config
    )
    
    if not stats.get('trello_enabled'):
        print("Error: Trello data not available.", file=sys.stderr)
        sys.exit(1)
    
    # Step 2: Generate invoice line items (SAME function as invoice generator)
    # This uses the exact same logic, exclusions, and calculations as the invoice
    print("Generating invoice line items (using same logic as invoice generator)...", file=sys.stderr)
    line_items = generate_invoice_line_items(stats, config)
    
    if not line_items:
        print("Warning: No line items found. Check your date range and Trello board.", file=sys.stderr)
        sys.exit(1)
    
    # Format for Google Sheets with actual work dates
    print("Formatting timesheet data with actual work dates...", file=sys.stderr)
    rows = format_line_items_for_timesheet(
        line_items=line_items,
        stats=stats,  # Pass stats to extract dates from commits/comments
        since_date=args.since_date,  # Filter dates to only include work on/after this date
        board=board_name,
        project=project_name
    )
    
    if args.tsv:
        # Output to TSV file - user can open file and copy/paste from there
        with open(args.tsv, 'w', encoding='utf-8') as f:
            for row in rows:
                clean_row = [str(cell).replace('\n', ' ').replace('\r', '').replace('\t', ' ') for cell in row]
                f.write('\t'.join(clean_row) + '\n')
        print(f"TSV file written to: {args.tsv}", file=sys.stderr)
        print("1. Open the file in a text editor (Notepad, VS Code, etc.)", file=sys.stderr)
        print("2. Select ALL and copy (Ctrl+A, Ctrl+C)", file=sys.stderr)
        print("3. Paste into Google Sheets (Ctrl+V) - columns will separate automatically!", file=sys.stderr)
    elif args.csv:
        with open(args.csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"CSV file written to: {args.csv}", file=sys.stderr)
        print("You can import this file into Google Sheets: File > Import > Upload", file=sys.stderr)
    else:
        # Default: output as TSV (tab-separated) to stdout
        output_tsv_to_stdout(rows)
        print("\n" + "="*70, file=sys.stderr)
        print("COPY/PASTE:", file=sys.stderr)
        print("="*70, file=sys.stderr)
        print("1. Select ALL the data lines above (tab-separated)", file=sys.stderr)
        print("2. Copy (Ctrl+C)", file=sys.stderr)
        print("3. Paste into Google Sheets (Ctrl+V)", file=sys.stderr)
        print("\nIf that doesn't work, use: --tsv timesheet.tsv", file=sys.stderr)
        print("Then open the file and copy from there (guaranteed to work!)", file=sys.stderr)
        print("="*70, file=sys.stderr)

if __name__ == '__main__':
    main()
