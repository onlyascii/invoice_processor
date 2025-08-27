"""Command line interface for invoice processing."""

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ai_context import ProcessingContext
from .processor import InvoiceProcessor
from .tui import InvoiceProcessorApp
from .utils import get_pdf_files


class CLIInterface:
    """Command line interface for the invoice processor."""

    def __init__(self):
        """Initialize the CLI interface."""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser."""
        parser = argparse.ArgumentParser(
            description="Process one or more invoices using an AI model."
        )

        # File input group (mutually exclusive)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--file",
            type=str,
            help="The path to a single PDF file to be processed."
        )
        group.add_argument(
            "--folder",
            type=str,
            help="The path to a folder containing PDF files to be processed."
        )

        # Model configuration
        parser.add_argument(
            "--model",
            type=str,
            default="qwen3",
            help="The model to use for processing."
        )
        parser.add_argument(
            "--ollama-url",
            type=str,
            default="http://localhost:11434/v1",
            help="The base URL for the Ollama API."
        )

        # Output configuration
        parser.add_argument(
            "--output-dir",
            type=str,
            default="processed_invoices",
            help="The directory to save the renamed invoice files. Defaults to 'processed_invoices'."
        )
        parser.add_argument(
            "--move",
            action="store_true",
            help="Move successfully processed files to the output directory instead of copying."
        )

        # Vendor configuration
        parser.add_argument(
            "--vendor-override",
            type=str,
            help="Override the vendor name for all processed invoices. The AI-detected vendor will become an alias."
        )

        # Logging configuration
        parser.add_argument(
            "--log-file",
            type=str,
            default="processing_log.txt",
            help="Path to the log file for performance metrics."
        )
        parser.add_argument(
            "--args-log-file",
            type=str,
            default=None,
            help="Path to a file to log script arguments in JSONL format. If provided, enables argument logging."
        )

        # UI options
        parser.add_argument(
            "--tui",
            action="store_true",
            help="Enable Textual TUI for interactive folder processing."
        )

        return parser

    async def run(self) -> None:
        """Run the CLI application."""
        args = self.parser.parse_args()

        # Create AI processing context
        context = ProcessingContext(
            model_name=args.model,
            ollama_url=args.ollama_url
        )

        # Handle TUI mode
        if args.tui:
            await self._run_tui_mode(args, context)
        else:
            await self._run_cli_mode(args, context)

    async def _run_tui_mode(self, args: argparse.Namespace, context: ProcessingContext) -> None:
        """Run in TUI mode."""
        if not args.folder:
            print("Error: --tui mode is only available with --folder.")
            return

        if not os.path.isdir(args.folder):
            print(f"Error: Folder not found at '{args.folder}'")
            return

        app = InvoiceProcessorApp(
            folder_path=args.folder,
            context=context,
            move_files=args.move,
            output_dir=args.output_dir,
            vendor_override=getattr(args, 'vendor_override', None)
        )
        await app.run_async()

    async def _run_cli_mode(self, args: argparse.Namespace, context: ProcessingContext) -> None:
        """Run in CLI mode."""
        self._setup_logging(args.log_file)

        total_start_time = time.time()
        processor = InvoiceProcessor(context, vendor_override=getattr(args, 'vendor_override', None))
        files_processed = []

        if args.file:
            # Single file processing
            files_processed = [args.file]
            result = await processor.process_single_invoice(
                args.file, args.output_dir, args.move
            )
            if result:
                logging.info(f"Successfully processed: {result}")

        elif args.folder:
            # Folder processing
            if not os.path.isdir(args.folder):
                logging.error(f"Error: Folder not found at '{args.folder}'")
                return

            pdf_files = get_pdf_files(args.folder)
            files_processed = pdf_files

            if pdf_files:
                logging.info(f"Found {len(pdf_files)} PDF files. Processing concurrently...")
                results = await processor.process_multiple_invoices(
                    pdf_files, args.output_dir, args.move
                )
                successful = sum(1 for r in results if r is not None)
                logging.info(f"Successfully processed {successful}/{len(pdf_files)} files.")
            else:
                logging.info(f"No PDF files found in '{args.folder}'.")

        total_duration = time.time() - total_start_time
        logging.info(f"Total execution time: {total_duration:.2f} seconds")

        # Log arguments and performance if requested
        if args.args_log_file:
            self._log_run_info(args, files_processed, total_duration)

    def _setup_logging(self, log_file: str) -> None:
        """Set up logging for CLI mode."""
        # Remove existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Configure logging to write to a file and the console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            filename=log_file,
            filemode='a'  # Append to the log file on each run
        )

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(console_handler)

        # Silence noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("ollama").setLevel(logging.WARNING)

    def _log_run_info(
        self,
        args: argparse.Namespace,
        files_processed: list[str],
        total_duration: float
    ) -> None:
        """Log run information to a separate file."""
        try:
            run_info = {
                "timestamp": datetime.now().isoformat(),
                "arguments": vars(args),
                "files_processed": len(files_processed),
                "total_duration_seconds": round(total_duration, 2)
            }

            log_file_path = args.args_log_file
            log_data = []

            # Read existing data if the file exists and is not empty
            if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    try:
                        log_data = json.load(f)
                        if not isinstance(log_data, list):
                            logging.warning(
                                f"Log file '{log_file_path}' does not contain a JSON array. "
                                "It will be overwritten."
                            )
                            log_data = []
                    except json.JSONDecodeError:
                        logging.warning(
                            f"Could not decode JSON from '{log_file_path}'. "
                            "The file will be overwritten."
                        )
                        log_data = []

            # Append new run info
            log_data.append(run_info)

            # Write the updated data back to the file
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=4)

        except Exception as e:
            logging.error(f"Error: Could not write to arguments log file: {e}")


async def main() -> None:
    """Main entry point for the CLI application."""
    cli = CLIInterface()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
