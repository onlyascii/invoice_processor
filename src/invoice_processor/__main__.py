"""Entry point for running invoice_processor as a module."""

import asyncio
from .cli import main

if __name__ == "__main__":
    asyncio.run(main())
