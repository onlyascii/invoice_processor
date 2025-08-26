#!/usr/bin/env python3
"""
Standalone entry point script for invoice processor.
This can be used when the package isn't installed.
"""

import sys
import os
import asyncio

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from invoice_processor.cli import main

if __name__ == "__main__":
    asyncio.run(main())
