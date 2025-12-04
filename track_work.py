#!/usr/bin/env python3
"""
Main entry point for work time tracker
This script allows running track_work from the root directory
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import src as a package
sys.path.insert(0, str(Path(__file__).parent))

# Import and run main from the src package
from src.track_work import main

if __name__ == '__main__':
    main()
