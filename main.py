"""Legacy main.py - maintained for backward compatibility.

This file imports and delegates to the new modular structure.
Consider using the CLI directly via: python -m src.invoice_processor.cli
"""

import asyncio
from src.invoice_processor.cli import main

if __name__ == "__main__":
    # Run the async main function from the new modular CLI
    asyncio.run(main())
