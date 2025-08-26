"""Main TUI application for interactive invoice processing."""

import asyncio
import logging
import os
from typing import Set

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, RichLog, SelectionList, ProgressBar, Static
from textual.binding import Binding
from textual import work
from rich.text import Text

from ..ai_context import ProcessingContext
from ..processor import InvoiceProcessor
from ..monitoring import SystemMonitor
from ..utils import get_pdf_files, get_file_basename
from .logging_handler import TuiLogHandler


class InvoiceProcessorApp(App):
    """A Textual app for interactively processing invoices."""

    CSS = """
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    SelectionList {
        width: 40%;
        border-right: solid $accent;
    }
    #right-panel {
        width: 60%;
        layout: vertical;
    }
    RichLog {
        height: 1fr;
    }
    #progress-container {
        height: 3;
        margin: 1 0;
    }
    #status-bar {
        height: 1;
        background: $surface;
        color: $text;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("p", "process_selected", "Process Selected"),
        Binding("space", "toggle_selection", "Toggle Selection", show=False),
        Binding("r", "refresh_files", "Refresh Files"),
    ]

    def __init__(
        self,
        folder_path: str,
        context: ProcessingContext,
        move_files: bool,
        output_dir: str
    ):
        """
        Initialize the TUI application.

        Args:
            folder_path: Path to folder containing PDF files
            context: AI processing context
            move_files: Whether to move or copy processed files
            output_dir: Output directory for processed files
        """
        super().__init__()
        self.folder_path = folder_path
        self.processing_context = context
        self.move_files = move_files
        self.output_dir = output_dir
        self.selected_files: Set[str] = set()
        self.files_to_process: list[str] = []
        self.is_processing = False
        self.total_files_to_process = 0
        self.files_processed = 0

        # Initialize processor
        self.processor = InvoiceProcessor(context)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="main-container"):
            yield SelectionList[str](id="file_list")
            with Vertical(id="right-panel"):
                with Container(id="progress-container"):
                    yield ProgressBar(id="progress_bar", show_eta=True)
                yield RichLog(id="log_window", wrap=True, highlight=True)
                yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.refresh_file_list()
        self._setup_logging()
        self._log_initial_message()
        self.update_system_monitor()

    def _setup_logging(self) -> None:
        """Set up logging to use the TUI handler."""
        log_window = self.query_one(RichLog)
        tui_handler = TuiLogHandler(log_window)

        # Remove all other handlers to only log to the TUI
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.addHandler(tui_handler)
        root_logger.setLevel(logging.INFO)

    def _log_initial_message(self) -> None:
        """Log the initial welcome message."""
        log_window = self.query_one(RichLog)
        log_window.write(
            "App initialized. Press 'space' to select files, 'p' to process, "
            "'r' to refresh, 'q' to quit."
        )

    def refresh_file_list(self) -> None:
        """Refresh the file list from the folder."""
        selection_list = self.query_one(SelectionList)
        selection_list.clear_options()

        if not os.path.isdir(self.folder_path):
            self.query_one(RichLog).write(
                Text.from_markup(f"[bold red]Error: Folder not found at '{self.folder_path}'[/bold red]")
            )
            return

        self.files_to_process = get_pdf_files(self.folder_path)

        if not self.files_to_process:
            self.query_one(RichLog).write(
                Text.from_markup(f"[bold yellow]No PDF files found in '{self.folder_path}'.[/bold yellow]")
            )
            return

        for file_path in self.files_to_process:
            selection_list.add_option((get_file_basename(file_path), file_path))

        self.query_one(RichLog).write(
            Text.from_markup(f"[bold]Found {len(self.files_to_process)} PDF files.[/bold]")
        )

    def action_refresh_files(self) -> None:
        """Refresh the file list."""
        if not self.is_processing:
            self.refresh_file_list()
            self.query_one(RichLog).write(
                Text.from_markup("[bold blue]File list refreshed.[/bold blue]")
            )
        else:
            self.query_one(RichLog).write(
                Text.from_markup("[bold red]Cannot refresh while processing.[/bold red]")
            )

    @work(exclusive=False, group="system_monitor")
    async def update_system_monitor(self) -> None:
        """Update system resource monitoring in the status bar."""
        while True:
            try:
                # Check if app is still running
                if not self.is_running:
                    break

                stats = SystemMonitor.get_system_stats()
                status_text = SystemMonitor.format_stats_for_display(stats)
                self.query_one("#status-bar", Static).update(status_text)
            except Exception:
                # Silently handle any errors in system monitoring
                pass
            await asyncio.sleep(2)  # Update every 2 seconds

    def action_toggle_selection(self) -> None:
        """Toggle the selection of the currently highlighted file."""
        if self.is_processing:
            self.query_one(RichLog).write(
                Text.from_markup("[bold red]Cannot change selection while processing.[/bold red]")
            )
            return

        selection_list = self.query_one(SelectionList)
        if selection_list.highlighted_child:
            selection_list.toggle_option(selection_list.highlighted_child.id)

    def action_process_selected(self) -> None:
        """Start processing the selected files."""
        if self.is_processing:
            self.query_one(RichLog).write(
                Text.from_markup("[bold red]Processing already in progress.[/bold red]")
            )
            return

        selection_list = self.query_one(SelectionList)
        selected_items = selection_list.selected

        if not selected_items:
            self.query_one(RichLog).write(
                Text.from_markup("[bold red]No files selected. Press 'space' to select files.[/bold red]")
            )
            return

        self.total_files_to_process = len(selected_items)
        self.files_processed = 0
        self.is_processing = True

        # Reset progress bar
        progress_bar = self.query_one(ProgressBar)
        progress_bar.update(total=self.total_files_to_process, progress=0)

        files_to_run = list(selected_items)
        self.query_one(RichLog).write(
            Text.from_markup(f"[bold]Starting processing for {len(files_to_run)} files...[/bold]")
        )
        self.run_processing(files_to_run)

    @work(exclusive=True, group="processing")
    async def run_processing(self, files: list[str]) -> None:
        """The background worker for processing invoice files."""
        try:
            for i, file_path in enumerate(files):
                logging.info(f"Processing file {i+1}/{len(files)}: {get_file_basename(file_path)}")

                # Process the file
                result = await self.processor.process_single_invoice(
                    file_path, self.output_dir, self.move_files
                )

                # Update progress
                self.files_processed += 1
                progress_bar = self.query_one(ProgressBar)
                progress_bar.update(progress=self.files_processed)

            logging.info("\n--- [bold green]All selected files processed.[/bold green] ---")

        finally:
            self.is_processing = False
            # Refresh file list to show updated state (especially if files were moved)
            self.refresh_file_list()
            logging.info("[bold blue]File list updated.[/bold blue]")
