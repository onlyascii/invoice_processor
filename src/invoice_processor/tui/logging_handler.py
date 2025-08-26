"""Custom logging handler for TUI applications."""

import logging

from textual.widgets import RichLog
from rich.text import Text


class TuiLogHandler(logging.Handler):
    """A logging handler that sends records to a Textual RichLog widget."""

    def __init__(self, rich_log: RichLog):
        """
        Initialize the TUI log handler.

        Args:
            rich_log: The RichLog widget to write to
        """
        super().__init__()
        self.rich_log = rich_log

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the RichLog widget.

        Args:
            record: The log record to emit
        """
        # Use the raw message and render Rich markup
        msg = record.getMessage()

        # Parse Rich markup and create a Rich Text object
        try:
            rich_text = Text.from_markup(msg)
            self.rich_log.write(rich_text)
        except Exception:
            # If markup parsing fails, fall back to plain text
            self.rich_log.write(msg)
