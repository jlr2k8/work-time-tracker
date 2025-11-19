#!/usr/bin/env python3
"""
Simple projection based on existing invoice data
"""

from datetime import datetime, timedelta

def project_from_invoice(invoice_amount: float, start_date: str, end_date: str, 
                         target_date: str, hourly_rate: float = 80.0):
    """
    Project future earnings based on invoice data
    
    Args:
        invoice_amount: Amount billed in the invoice period
        start_date: Start date of invoice period (YYYY-MM-DD)
        end_date: End date of invoice period (YYYY-MM-DD)
        target_date: Date to project to (YYYY-MM-DD)
        hourly_rate: Hourly rate (default: $80)
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    target = datetime.strptime(target_date, "%Y-%m-%d")
    today = datetime.now()
    
    # Calculate days in invoice period
    days_in_period = (end - start).days + 1
    
    # Calculate hours from invoice amount
    hours_in_period = invoice_amount / hourly_rate
    
    # Calculate daily rate
    daily_rate = hours_in_period / days_in_period if days_in_period > 0 else 0
    daily_amount = invoice_amount / days_in_period if days_in_period > 0 else 0
    
    # Calculate days from start to target
    days_to_target = (target - start).days + 1
    
    # Project total
    projected_hours = daily_rate * days_to_target
    projected_amount = daily_amount * days_to_target
    
    print(f"\n{'='*70}")
    print("INVOICE-BASED PROJECTION")
    print(f"{'='*70}")
    print(f"Invoice Period: {start_date} to {end_date}")
    print(f"  Days: {days_in_period}")
    print(f"  Amount: ${invoice_amount:,.2f}")
    print(f"  Hours: {hours_in_period:.2f}h")
    print(f"  Daily rate: ${daily_amount:,.2f}/day ({daily_rate:.2f}h/day)")
    print()
    print(f"Projection to {target_date}:")
    print(f"  Days from start: {days_to_target}")
    print(f"  Projected hours: {projected_hours:.2f}h")
    print(f"  Projected amount: ${projected_amount:,.2f}")
    print()
    print(f"{'='*70}")
    print(f"ESTIMATE: ${projected_amount:,.2f} by {target_date}")
    print(f"{'='*70}")
    print()

if __name__ == "__main__":
    import sys
    
    # Default: Nov 10-19, $1,880.80, project to Nov 30
    invoice_amount = 1880.80
    start_date = "2025-11-10"
    end_date = "2025-11-19"
    target_date = "2025-11-30"
    hourly_rate = 80.0
    
    if len(sys.argv) >= 2:
        invoice_amount = float(sys.argv[1])
    if len(sys.argv) >= 3:
        start_date = sys.argv[2]
    if len(sys.argv) >= 4:
        end_date = sys.argv[3]
    if len(sys.argv) >= 5:
        target_date = sys.argv[4]
    if len(sys.argv) >= 6:
        hourly_rate = float(sys.argv[5])
    
    project_from_invoice(invoice_amount, start_date, end_date, target_date, hourly_rate)

