#!/usr/bin/env python3
"""
Standalone entry point script for invoice processor.
This can be used when the package isn't installed.
"""

import sys
import os
import asyncio

# Add the project root to Python path so we can import our modules
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from src.invoice_processor.cli import main

if __name__ == "__main__":
    asyncio.run(main())
