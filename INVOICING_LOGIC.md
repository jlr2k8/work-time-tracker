# Invoice Generation Logic Documentation

## Overview
This document explains how the work time tracker calculates billable hours and generates invoices.

## Key Concepts

### Comment Hours vs. Commit Hours

**Comment Hours:**
- Hours **reported in Trello card comments** (e.g., "worked 3 hours", "spent 2h", "30 min")
- These represent **actual time worked** that you manually log
- Extracted from comments like:
  - "worked 3 hours"
  - "spent 2h"
  - "worked 30 min" (converted to 0.5h)
- **NOT** the time spent writing the comment itself
- Usually whole numbers (1h, 2h, 3h, etc.) because they're manually logged

**Commit Hours:**
- Hours **calculated from git commits** based on lines of code changed
- Formula: `lines_changed / lines_per_hour` (varies by complexity: 200-400 lines/hour)
- These are **estimates** based on code volume
- Often fractional (2.25h, 11.53h, etc.) because they're calculated from code metrics

## Hour Calculation Logic

### For Cards with Both Comment Hours AND Commit Hours

**Weighted Average Formula:**
```
total_hours = (comment_hours × 0.8) + (commit_hours × 0.2)
```

**Why?**
- Comment hours (80% weight) = manually logged time, trusted as source of truth
- Commit hours (20% weight) = validation/cross-check to catch under-logged time
- Balances manual logging with code-based validation

**Example - Card #99:**
- Comment hours: 8.00h (from comments: "worked 3h", "worked 3h again", "worked 2h")
- Commit hours: 25.66h (calculated from 5,186 lines of code)
- Calculation: (8.00 × 0.8) + (25.66 × 0.2) = 6.4 + 5.132 = **11.532h**
- Billed: 11.532h × $80/hr = **$922.56**

### For Cards with Only Comment Hours

**Uses comment hours directly:**
```
total_hours = comment_hours
```

**Example - Card #37:**
- Comment hours: 3.00h
- Commit hours: 0.00h (no matching commits)
- Billed: 3.00h × $80/hr = **$240.00**

### For Cards with Only Commit Hours

**Uses commit hours directly:**
```
total_hours = commit_hours
```

**Example - Card #80:**
- Comment hours: 0.00h (no comments with hours)
- Commit hours: 2.25h (calculated from 449 lines)
- Billed: 2.25h × $80/hr = **$180.00**

## Why Some Line Items Have Fractional Amounts

**Cards with only comment hours OR only commit hours:**
- Usually whole numbers → clean $80 increments ($80, $160, $240, etc.)

**Cards with BOTH comment and commit hours:**
- Weighted average creates fractional hours → fractional dollar amounts
- Example: 11.532h → $922.56 (not a clean $80 multiple)

**Cards with only commit hours:**
- Can also be fractional because they're calculated from lines of code
- Example: 2.25h → $180.00

## Comment Parsing

The system extracts hours from Trello comments using these patterns:

**Hour patterns:**
- "1.5h", "2 hours", "3 hrs"
- "spent 1.5h", "worked 2h"
- "hours: 1.5"

**Minute patterns (converted to hours):**
- "30 min" → 0.5h
- "worked 30 min" → 0.5h
- "spent 45 minutes" → 0.75h

**Important:** The system extracts the **hours you report working**, not the time spent writing the comment.

## Date Filtering

Comments are filtered by the `--since-date` parameter:
- Only comments dated on or after the specified date are counted
- Example: `--since-date 2025-11-10` only counts comments from Nov 10 onwards
- This ensures you only bill for work in the specified period

## Card Matching

Cards are matched to commits via:
1. **Branch names** (highest priority): `feature/99-...`, `bugfix-123-...`
2. **Commit messages**: References like `#99`, `T99`
3. **Fuzzy matching**: Keyword matching between commit messages and card names

## Common Questions

**Q: Why is card #99 billing $922.56 instead of $640 (8h × $80)?**
A: The weighted average includes 20% of commit hours (25.66h), adding 5.132h to your 8h logged time, resulting in 11.532h total.

**Q: Why do some cards have fractional amounts?**
A: Cards with both comment and commit hours use a weighted average, which creates fractional hours. Cards with only one source usually have whole numbers.

**Q: Does the system count time spent writing comments?**
A: No. It extracts hours **reported in comments** (e.g., "worked 3h"), not time spent writing the comment itself.

**Q: What if I log 2h but commits show 25h?**
A: The weighted average will use: (2h × 0.8) + (25h × 0.2) = 1.6h + 5h = 6.6h. This prevents under-billing while still respecting your logged time.

**Q: Can I change the 80/20 weighting?**
A: Yes, the weights are in `track_work.py` - Adjust the 0.8 and 0.2 values as needed.

## Summary

- **Comment hours** = manually logged time (source of truth)
- **Commit hours** = calculated estimates (validation)
- **Weighted average** = balances both to prevent under-billing
- **Fractional amounts** = result from weighted averages or calculated commit hours
- **Comment parsing** = extracts hours you report, not time writing comments