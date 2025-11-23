#!/usr/bin/env python3
"""
Generate an example invoice PDF with fake data for demonstration purposes
"""

from datetime import datetime, timedelta
from invoice_generator import InvoiceGenerator, create_invoice_from_tracking_data
from config import Config

def generate_example_invoice():
    """Generate an example invoice with realistic fake data"""
    
    # Create fake stats dictionary
    today = datetime.now()
    start_date = today - timedelta(days=30)
    
    # Create fake commits data with proper structure
    # Add lines_changed and _match_type fields
    fake_commits = [
        {
            'hash': 'a1b2c3d',
            'date': (start_date + timedelta(days=2)).strftime('%Y-%m-%d'),
            'message': 'feat: Implement user authentication system [Trello-101]',
            'author': 'John Doe',
            'lines_added': 450,
            'lines_deleted': 120,
            'lines_changed': 570,  # lines_added + lines_deleted
            'files_changed': 8,
            '_match_type': 'explicit'  # Explicit Trello reference
        },
        {
            'hash': 'e4f5g6h',
            'date': (start_date + timedelta(days=3)).strftime('%Y-%m-%d'),
            'message': 'fix: Resolve login bug [Trello-101]',
            'author': 'John Doe',
            'lines_added': 85,
            'lines_deleted': 45,
            'lines_changed': 130,
            'files_changed': 2,
            '_match_type': 'explicit'
        },
        {
            'hash': 'i7j8k9l',
            'date': (start_date + timedelta(days=5)).strftime('%Y-%m-%d'),
            'message': 'feat: Add payment processing integration [Trello-102]',
            'author': 'John Doe',
            'lines_added': 680,
            'lines_deleted': 200,
            'lines_changed': 880,
            'files_changed': 12,
            '_match_type': 'explicit'
        },
        {
            'hash': 'm1n2o3p',
            'date': (start_date + timedelta(days=7)).strftime('%Y-%m-%d'),
            'message': 'feat: Implement dashboard analytics [Trello-103]',
            'author': 'John Doe',
            'lines_added': 520,
            'lines_deleted': 150,
            'lines_changed': 670,
            'files_changed': 10,
            '_match_type': 'explicit'
        },
        {
            'hash': 'q4r5s6t',
            'date': (start_date + timedelta(days=10)).strftime('%Y-%m-%d'),
            'message': 'refactor: Optimize database queries [Trello-104]',
            'author': 'John Doe',
            'lines_added': 320,
            'lines_deleted': 180,
            'lines_changed': 500,
            'files_changed': 6,
            '_match_type': 'explicit'
        },
        {
            'hash': 'u7v8w9x',
            'date': (start_date + timedelta(days=12)).strftime('%Y-%m-%d'),
            'message': 'feat: Add email notification system [Trello-105]',
            'author': 'John Doe',
            'lines_added': 380,
            'lines_deleted': 90,
            'lines_changed': 470,
            'files_changed': 7,
            '_match_type': 'explicit'
        },
        {
            'hash': 'y1z2a3b',
            'date': (start_date + timedelta(days=15)).strftime('%Y-%m-%d'),
            'message': 'fix: Update API documentation [Trello-106]',
            'author': 'John Doe',
            'lines_added': 150,
            'lines_deleted': 30,
            'lines_changed': 180,
            'files_changed': 3,
            '_match_type': 'explicit'
        },
        # Add more commits for better daily distribution
        {
            'hash': 'c1d2e3f',
            'date': (start_date + timedelta(days=4)).strftime('%Y-%m-%d'),
            'message': 'test: Add unit tests for auth module',
            'author': 'John Doe',
            'lines_added': 200,
            'lines_deleted': 10,
            'lines_changed': 210,
            'files_changed': 5,
            '_match_type': 'fuzzy'  # Fuzzy match to card 101
        },
        {
            'hash': 'g4h5i6j',
            'date': (start_date + timedelta(days=8)).strftime('%Y-%m-%d'),
            'message': 'feat: Add chart visualizations to dashboard',
            'author': 'John Doe',
            'lines_added': 180,
            'lines_deleted': 20,
            'lines_changed': 200,
            'files_changed': 4,
            '_match_type': 'fuzzy'  # Fuzzy match to card 103
        },
        # Add more commits across more days for better chart visualization
        {
            'hash': 'k1l2m3n',
            'date': (start_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'message': 'chore: Setup project structure',
            'author': 'John Doe',
            'lines_added': 50,
            'lines_deleted': 5,
            'lines_changed': 55,
            'files_changed': 3,
            '_match_type': 'fuzzy'
        },
        {
            'hash': 'o4p5q6r',
            'date': (start_date + timedelta(days=6)).strftime('%Y-%m-%d'),
            'message': 'fix: Resolve payment gateway timeout',
            'author': 'John Doe',
            'lines_added': 120,
            'lines_deleted': 40,
            'lines_changed': 160,
            'files_changed': 2,
            '_match_type': 'fuzzy'  # Fuzzy match to card 102
        },
        {
            'hash': 's7t8u9v',
            'date': (start_date + timedelta(days=9)).strftime('%Y-%m-%d'),
            'message': 'refactor: Improve query performance',
            'author': 'John Doe',
            'lines_added': 90,
            'lines_deleted': 60,
            'lines_changed': 150,
            'files_changed': 4,
            '_match_type': 'fuzzy'  # Fuzzy match to card 104
        },
        {
            'hash': 'w1x2y3z',
            'date': (start_date + timedelta(days=11)).strftime('%Y-%m-%d'),
            'message': 'docs: Update API documentation',
            'author': 'John Doe',
            'lines_added': 80,
            'lines_deleted': 15,
            'lines_changed': 95,
            'files_changed': 2,
            '_match_type': 'fuzzy'  # Fuzzy match to card 106
        },
        {
            'hash': 'a4b5c6d',
            'date': (start_date + timedelta(days=14)).strftime('%Y-%m-%d'),
            'message': 'test: Add integration tests',
            'author': 'John Doe',
            'lines_added': 150,
            'lines_deleted': 20,
            'lines_changed': 170,
            'files_changed': 6,
            '_match_type': 'fuzzy'
        },
        {
            'hash': 'e7f8g9h',
            'date': (start_date + timedelta(days=16)).strftime('%Y-%m-%d'),
            'message': 'feat: Add error handling',
            'author': 'John Doe',
            'lines_added': 100,
            'lines_deleted': 25,
            'lines_changed': 125,
            'files_changed': 3,
            '_match_type': 'fuzzy'
        },
    ]
    
    # Create fake stats with Trello integration
    stats = {
        'commit_count': len(fake_commits),
        'estimated_hours': 19.37,
        'estimated_amount': 1549.60,  # 19.37h * $80
        'hourly_rate': 80.0,
        'commits': fake_commits,
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': today.strftime('%Y-%m-%d')
        },
        'trello_enabled': True,
        'estimation_details': {
            'matched_cards': [
                {
                    'card': {
                        'id': 'abc123',
                        'idShort': 101,  # Task number for extraction
                        'name': 'Implement user authentication system #101',
                        'url': 'https://trello.com/c/abc123',
                        'actions': []  # No comment hours for this card
                    },
                    'commit_based_hours': 3.5,
                    'comment_hours': 0.0,
                    'total_hours': 3.5,
                    'commits': fake_commits[:2] + [fake_commits[7]],  # Include fuzzy match
                    'estimated_hours': 4.0
                },
                {
                    'card': {
                        'id': 'def456',
                        'idShort': 102,
                        'name': 'Add payment processing integration #102',
                        'url': 'https://trello.com/c/def456',
                        'actions': []  # No comment hours
                    },
                    'commit_based_hours': 5.2,
                    'comment_hours': 0.0,
                    'total_hours': 5.2,
                    'commits': [fake_commits[2]],
                    'estimated_hours': 6.0
                },
                {
                    'card': {
                        'id': 'ghi789',
                        'idShort': 103,
                        'name': 'Implement dashboard analytics #103',
                        'url': 'https://trello.com/c/ghi789',
                        'actions': []  # No comment hours for this card
                    },
                    'commit_based_hours': 4.1,
                    'comment_hours': 0.0,
                    'total_hours': 4.1,
                    'commits': [fake_commits[3], fake_commits[8]],  # Include fuzzy match
                    'estimated_hours': 4.0
                },
                {
                    'card': {
                        'id': 'jkl012',
                        'idShort': 104,
                        'name': 'Optimize database queries #104',
                        'url': 'https://trello.com/c/jkl012',
                        'actions': []  # No comment hours
                    },
                    'commit_based_hours': 2.8,
                    'comment_hours': 0.0,
                    'total_hours': 2.8,
                    'commits': [fake_commits[4]],
                    'estimated_hours': 3.0
                },
                {
                    'card': {
                        'id': 'mno345',
                        'idShort': 105,
                        'name': 'Add email notification system #105',
                        'url': 'https://trello.com/c/mno345',
                        'actions': [
                            {
                                'type': 'commentCard',
                                'date': (start_date + timedelta(days=12)).isoformat() + 'T10:30:00.000Z',
                                'data': {
                                    'text': 'worked 1.5h on email service setup'
                                }
                            },
                            {
                                'type': 'commentCard',
                                'date': (start_date + timedelta(days=13)).isoformat() + 'T14:15:00.000Z',
                                'data': {
                                    'text': 'spent 1h testing email delivery'
                                }
                            }
                        ]
                    },
                    'commit_based_hours': 3.2,
                    'comment_hours': 2.5,  # Example of comment hours (manually logged)
                    'total_hours': 2.57,  # Weighted: (2.5 * 0.9) + (3.2 * 0.1) = 2.25 + 0.32 = 2.57
                    'commits': [fake_commits[5]],
                    'estimated_hours': 4.0
                },
                {
                    'card': {
                        'id': 'pqr678',
                        'idShort': 106,
                        'name': 'Update API documentation #106',
                        'url': 'https://trello.com/c/pqr678',
                        'actions': []  # No comment hours
                    },
                    'commit_based_hours': 1.2,
                    'comment_hours': 0.0,
                    'total_hours': 1.2,
                    'commits': [fake_commits[6]],
                    'estimated_hours': 1.5
                }
            ],
            'unmatched_cards': [],
            'unmatched_commits': [
                {
                    'hash': 'z9y8x7w',
                    'date': (start_date + timedelta(days=18)).strftime('%Y-%m-%d'),
                    'message': 'chore: Update dependencies',
                    'author': 'John Doe',
                    'lines_added': 30,
                    'lines_deleted': 10,
                    'lines_changed': 40,
                    'files_changed': 1
                }
            ],
            'unmatched_hours': 0.16,  # Small amount of unmatched work
            'estimated_hours': 19.53  # Total work (matched + unmatched)
        }
    }
    
    # Create fake line items
    config = Config()
    line_items = [
        {
            'task_number': '101',
            'description': 'Implement user authentication system - (2 commits, 330 lines)',
            'category': 'FEAT',
            'amount': 280.00  # 3.5h * $80
        },
        {
            'task_number': '102',
            'description': 'Add payment processing integration - (1 commit, 480 lines)',
            'category': 'FEAT',
            'amount': 416.00  # 5.2h * $80
        },
        {
            'task_number': '103',
            'description': 'Implement dashboard analytics - (1 commit, 370 lines)',
            'category': 'FEAT',
            'amount': 328.00  # 4.1h * $80
        },
        {
            'task_number': '104',
            'description': 'Optimize database queries - (1 commit, 140 lines)',
            'category': 'MAINT',
            'amount': 224.00  # 2.8h * $80
        },
        {
            'task_number': '105',
            'description': 'Add email notification system - (1 commit, 290 lines, 2.5h comments)',
            'category': 'FEAT',
            'amount': 205.60  # 2.57h * $80 (weighted average: 90% comment + 10% commit)
        },
        {
            'task_number': '106',
            'description': 'Update API documentation - (1 commit, 120 lines)',
            'category': 'DOCS',
            'amount': 96.00  # 1.2h * $80
        }
    ]
    
    # Create invoice generator with example sender/recipient info
    generator = InvoiceGenerator(
        sender_name="John Doe",
        sender_address="123 Developer St, San Francisco, CA 94102",
        sender_phone="(555) 123-4567",
        sender_email="john.doe@example.com",
        recipient_name="Acme Corporation",
        invoice_prefix="INV"
    )
    
    # Generate invoice
    invoice_date = today.strftime("%m/%d/%y")
    invoice_number = 1
    
    output_path = create_invoice_from_tracking_data(
        stats=stats,
        line_items=line_items,
        invoice_date=invoice_date,
        invoice_number=invoice_number,
        output_dir=".",
        generator=generator,
        include_breakdown=True  # Include detailed breakdown page
    )
    
    print(f"Example invoice generated: {output_path}")
    print(f"Invoice #: INV-001")
    print(f"Date: {invoice_date}")
    print(f"Total: ${sum(item['amount'] for item in line_items):,.2f}")
    print(f"Line items: {len(line_items)}")
    
    return output_path

if __name__ == '__main__':
    generate_example_invoice()

