# Work Time Tracker

An advanced Python script to analyze git commits and Trello tasks to estimate billable hours with high accuracy. Cross-validates git commit patterns against Trello task estimates for more reliable billing.

## Features

- **Git Commit Analysis**: Analyzes commit patterns, frequency, and messages to estimate work hours
- **Trello Integration**: Fetches Trello cards and extracts estimated hours from custom fields, labels, or descriptions
- **Smart Matching**: Automatically matches commits to Trello cards via commit messages
- **Cross-Validation**: Compares actual work (commits) against Trello estimates for accuracy
- **Comprehensive Reporting**: Shows matched/unmatched tasks, accuracy metrics, and detailed breakdowns

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Set up Trello integration:
   - Get your Trello API key from: https://trello.com/app-key
   - Generate a token by visiting: https://trello.com/1/authorize?expiration=never&scope=read&response_type=token&name=WorkTimeTracker&key=YOUR_API_KEY
   - Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your Trello credentials
   ```

## Project Structure

```
work-time-tracker/
├── src/                    # Core modules
│   ├── config.py          # Configuration management
│   ├── trello_client.py   # Trello API client
│   ├── invoice_generator.py # Invoice PDF generator
│   └── track_work.py      # Main tracking logic
├── scripts/                # Utility scripts
│   ├── check_assignment.py
│   ├── check_missing_estimates.py
│   ├── debug_card_hours.py
│   ├── debug_card_match.py
│   ├── generate_example_invoice.py
│   ├── get_card_links.py
│   ├── invoice_projection.py
│   ├── project_trajectory.py
│   ├── simple_projection.py
│   └── test_comment_parsing.py
├── invoices/              # Generated invoice PDFs
├── track_work.py          # Main entry point (convenience script)
├── README.md
└── requirements.txt
```

## Usage

### Basic Usage (Git Only)

```bash
python track_work.py <repo_path> [since_date] [author]
```

### With Trello Integration

```bash
python track_work.py <repo_path> [since_date] [author] [trello_board_id]
```

### Examples

```bash
# Analyze all commits since Nov 10, 2025
python track_work.py ../myproject 2025-11-10

# Filter by author (supports regex)
python track_work.py ../myproject 2025-11-10 "john|John"

# Monthly billing (start of month)
python track_work.py ../myproject 2025-11-01 "john|John"

# With Trello board ID (if not in .env)
python track_work.py ../myproject 2025-11-01 "john|John" abc123xyz
```

### Alternative: Run as Module

You can also run the main module directly:

```bash
python -m src.track_work <repo_path> [since_date] [author] [trello_board_id]
```

## Command-Line Flags

The script supports several optional flags for invoice generation and output control:

### Invoice Generation Flags

#### `--invoice`
Generate an invoice PDF from the tracking data.

```bash
# Generate invoice with default settings
python track_work.py ../myproject 2025-11-01 "john|John" --invoice
```

#### `--invoice-num <number>`
Set the invoice number (default: 1).

```bash
# Generate invoice #3
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --invoice-num 3
```

#### `--invoice-date <date>`
Set the invoice date in MM/DD/YY format (defaults to today). Also accepts YYYY-MM-DD format.

```bash
# Set invoice date to November 20, 2024
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --invoice-date 11/20/25

# Or use YYYY-MM-DD format
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --invoice-date 2025-11-20
```

#### `--invoice-output <directory>`
Specify the directory where the invoice PDF will be saved (default: current directory).

```bash
# Save invoice to a specific directory
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --invoice-output ./invoices
```

#### `--breakdown`
Include a detailed work breakdown page in the invoice PDF. This page shows work details, commit matching, and calculations.

```bash
# Generate invoice with detailed breakdown page
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --breakdown
```

#### `--skip-warnings`
Skip warnings about cards that have estimates but no tracked hours (commits or comments). By default, the script will stop invoice generation if such cards are found.

```bash
# Generate invoice even if some cards are missing hour tracking
python track_work.py ../myproject 2025-11-01 "john|John" --invoice --skip-warnings
```

### Complete Example

```bash
# Generate invoice #5 with custom date, breakdown page, and save to invoices folder
python track_work.py ../myproject 2025-11-01 "john|John" \
  --invoice \
  --invoice-num 5 \
  --invoice-date 11/30/24 \
  --invoice-output ./invoices \
  --breakdown \
  --skip-warnings
```

### Generating Example Invoices

To demonstrate the invoice system to stakeholders or test the invoice format, you can generate an example invoice with fake data:

```bash
python scripts/generate_example_invoice.py
```

This will create `invoice_INV_001.pdf` with:
- Sample line items with realistic task descriptions
- Complete breakdown page showing all visualizations
- Example commit data and Trello card matching
- All charts and graphs (pie charts, bar charts, daily timelines)
- Per-card breakdown with commit details

The example invoice uses fake data and won't affect your actual tracking. You can customize the sender/recipient information in the script if needed.

## Configuration

### Environment Variables

Set these in your `.env` file or as environment variables:

- `TRELLO_API_KEY`: Your Trello API key
- `TRELLO_API_TOKEN`: Your Trello API token
- `TRELLO_BOARD_ID`: (Optional) Default Trello board ID
- `TRELLO_MEMBER_ID`: (Optional) Your Trello member ID for filtering cards assigned to you
- `HOURLY_RATE`: (Optional) Hourly billing rate (default: 80.0)
- `EXCLUDED_CARDS`: (Optional) Comma-separated list of card numbers to exclude from invoices (e.g., "102,103")
- `SENDER_NAME`: (Optional) Your name for invoices (default: "Your Name")
- `SENDER_ADDRESS`: (Optional) Your address for invoices (default: "123 Main St, City, ST 12345")
- `SENDER_PHONE`: (Optional) Your phone number for invoices (default: "555-555-5555")
- `SENDER_EMAIL`: (Optional) Your email for invoices (default: "your.email@example.com")
- `RECIPIENT_NAME`: (Optional) Client/recipient name for invoices (default: "Client Name")
- `INVOICE_PREFIX`: (Optional) Prefix for invoice numbers (default: "INV")

### Trello Card Format

The script extracts estimated hours from Trello cards in multiple ways:

1. **Custom Fields**: If you use Trello custom fields for time estimates
2. **Labels**: Labels like "2h", "3.5h", "1.5 hours"
3. **Description**: Text like "Est: 2h", "Estimated: 3.5 hours", "Hours: 2.5"
4. **Card Name**: Card names with format "[2h]" or "[3.5 hours]"

### Commit Message Format

To match commits to Trello cards, include card references in commit messages:

- `[Trello-abc12345]` - Short card ID
- `https://trello.com/c/abc12345/...` - Full card URL
- `[Card Name]` - Card name in brackets (fuzzy matching)

Example commit messages:
```
feat: Add user authentication [Trello-abc12345]
fix: Resolve login bug [Card Name]
```

## How It Works

### Estimation Algorithm

1. **Git Analysis**:
   - Analyzes commits from **all branches** (including feature branches)
   - Groups commits by date to identify work sessions
   - Estimates hours based on lines of code changed:
     - Major features: ~200 lines/hour
     - Regular code: ~250 lines/hour
     - Documentation: ~400 lines/hour
   - Caps at 4 hours per day (realistic coding time)
   - Excludes merge commits and auto-generated files

2. **Trello Integration**:
   - Fetches cards from specified board
   - **Filters to only WIP and Done lists** (cards in other lists are excluded)
   - Extracts estimated hours from cards
   - Matches commits to cards via commit messages (explicit references or fuzzy keyword matching)
   - Extracts hours from card comments (for non-code work)
   - Cross-validates actual work vs estimates

3. **Final Calculation**:
   - Uses commit-based hours + comment hours for matched cards
   - **Unmatched commits are NOT billed** (only cards in WIP/Done with matching commits are invoiced)
   - All invoice items are tied to Trello cards for stakeholder clarity

### Accuracy Improvements

- **Only WIP/Done cards** are included in invoices (filters out cards not actively worked on)
- **Realistic hour estimation** based on lines of code (200-400 lines/hour depending on complexity)
- **Daily caps** prevent over-estimation (max 4 hours per day)
- **Comment hours** from Trello cards included for non-code work
- **Cross-validation** highlights discrepancies for review
- **Detailed metrics** show matching accuracy

## Output

The script prints:

### Basic Report
- Total commit count
- Estimated hours
- Hourly rate
- Estimated billable amount
- Recent commit summary

### With Trello Integration
- Cards filtered to WIP/Done lists
- Cards matched to commits
- Cards unmatched (estimated but no work done)
- Commits matched to cards
- Commits unmatched (work not in Trello - **not billed**)
- Breakdown by source (Trello vs commits)
- Matched card details with estimate vs actual comparison
- Accuracy indicators ([OK] = close match, [~] = discrepancy, [WARNING] = no commits)
- **Invoice only includes cards in WIP/Done lists with matching commits**

## Example Output

```
======================================================================
WORK TIME TRACKING REPORT
======================================================================
Author: john|John
Date Range: 2025-11-01 to 2025-11-30

Commits: 45
Estimated Hours: 18.5
Hourly Rate: $80.00
Estimated Amount: $1480.00

----------------------------------------------------------------------
TRELLO INTEGRATION ANALYSIS
----------------------------------------------------------------------
Cards with Estimates: 12
Cards Matched to Commits: 10
Cards Unmatched: 2
Commits Matched to Cards: 38
Commits Unmatched: 7

Breakdown:
  Trello-based Hours: 15.0
  Unmatched Commit Hours: 3.5
  Commit-only Estimate: 18.5

----------------------------------------------------------------------
MATCHED TRELLO CARDS:
----------------------------------------------------------------------
  [OK] Implement user authentication
      Est: 4h | Actual: 3.5h | Commits: 8
  ~ Add payment processing
      Est: 6h | Actual: 4.0h | Commits: 12
  ...
```

## Troubleshooting

### Trello Integration Not Working

1. Verify your API credentials are correct
2. Check that your board ID is correct (found in board URL)
3. Ensure your token has read access to the board
4. Check that cards have estimated hours in the expected format

### No Commits Found

1. Verify the repository path is correct
2. Script analyzes commits from **all branches** (uses `git log --all`)
3. Ensure commits exist since the specified date
4. Check author filter if using one

### Estimates Seem Off

1. Review the matched cards section to see estimate vs actual
2. Check for unmatched commits (work not tracked in Trello - these are NOT billed)
3. Verify cards are in WIP or Done lists (only those are included)
4. Check comment hours in Trello cards (they add to the total)
5. Consider adding more commit message references to Trello cards for better matching

### Cards Not Appearing in Invoice

1. **Card must be in WIP or Done list** (cards in other lists are excluded)
2. Card must have matching commits (unmatched cards are not billed)
3. Check if card is manually excluded via `EXCLUDED_CARDS` config
4. Verify commits have card references in commit messages for matching

## License

MIT