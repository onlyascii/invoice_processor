"""Core invoice processing functionality."""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from .ai_context import ProcessingContext
from .config import load_vendors_data, save_vendors_data, add_or_update_vendor_alias
from .utils import ensure_directory_exists, get_file_basename


class InvoiceProcessor:
    """Main invoice processing class."""

    def __init__(self, context: ProcessingContext, vendors_file: str = "vendors.yaml", vendor_override: Optional[str] = None):
        """
        Initialize the invoice processor.

        Args:
            context: AI processing context
            vendors_file: Path to the vendors configuration file
            vendor_override: Optional vendor name to override AI-detected vendors
        """
        self.context = context
        self.vendors_file = vendors_file
        self.vendor_override = vendor_override

    async def process_single_invoice(
        self,
        file_path: str,
        output_dir: str,
        move_file: bool = False
    ) -> Optional[str]:
        """
        Process a single PDF invoice file.

        Args:
            file_path: Path to the PDF file to process
            output_dir: Directory to save the processed file
            move_file: Whether to move (True) or copy (False) the file

        Returns:
            New filename if successful, None if failed
        """
        start_time = time.time()
        filename = get_file_basename(file_path)

        try:
            logging.info(f"Starting processing for: {filename}")

            # Extract text from PDF
            text_content = await self._extract_pdf_text(file_path)
            if not text_content:
                logging.warning(f"Could not extract any text from {filename}.")
                return None

            # Process with AI agents
            normalized_result, raw_result = await self._process_with_ai(text_content)
            if not normalized_result or not raw_result:
                logging.error(f"Failed to extract details for {filename}.")
                return None

            # Handle vendor override
            if self.vendor_override:
                # Store AI-detected vendor as the raw vendor name for alias tracking
                ai_detected_vendor = normalized_result.output.vendor
                # Update the normalized result to use the override
                normalized_result.output.vendor = self.vendor_override

                # Update vendor configuration: override becomes canonical, AI-detected becomes alias
                await self._update_vendor_config(
                    ai_detected_vendor,  # AI-detected vendor becomes the alias
                    self.vendor_override  # Override becomes the canonical name
                )

                # Also store the original raw vendor name as an alias
                if raw_result.output.verbatim_vendor_name != ai_detected_vendor:
                    await self._update_vendor_config(
                        raw_result.output.verbatim_vendor_name,
                        self.vendor_override
                    )

                logging.info(f"Using vendor override '{self.vendor_override}' instead of AI-detected '{ai_detected_vendor}'")
            else:
                # Normal processing: update vendor configuration with AI results
                await self._update_vendor_config(
                    raw_result.output.verbatim_vendor_name,
                    normalized_result.output.vendor
                )

            # Generate new filename and process file
            new_filename = normalized_result.output.to_filename()
            await self._process_file(file_path, output_dir, new_filename, move_file)

            return new_filename

        except Exception as e:
            logging.error(f"An error occurred while processing {filename}: {e}")
            return None
        finally:
            duration = time.time() - start_time
            logging.info(f"Finished processing {filename} in {duration:.2f} seconds.")

    async def process_multiple_invoices(
        self,
        file_paths: list[str],
        output_dir: str,
        move_files: bool = False,
        max_concurrent: int = 5
    ) -> list[Optional[str]]:
        """
        Process multiple invoice files concurrently.

        Args:
            file_paths: List of file paths to process
            output_dir: Directory to save processed files
            move_files: Whether to move or copy files
            max_concurrent: Maximum number of concurrent processes

        Returns:
            List of new filenames (None for failed processes)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(file_path: str) -> Optional[str]:
            async with semaphore:
                return await self.process_single_invoice(file_path, output_dir, move_files)

        tasks = [process_with_semaphore(fp) for fp in file_paths]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _extract_pdf_text(self, file_path: str) -> str:
        """
        Extract text content from a PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        try:
            reader = PdfReader(file_path)
            return "".join(page.extract_text() + "\n" for page in reader.pages)
        except Exception as e:
            logging.error(f"Error extracting text from {get_file_basename(file_path)}: {e}")
            return ""

    async def _process_with_ai(self, text_content: str) -> tuple:
        """
        Process text content with AI agents.

        Args:
            text_content: Extracted PDF text

        Returns:
            Tuple of (normalized_result, raw_result)
        """
        # Run both AI processing tasks concurrently
        norm_prompt = self.context.get_normalization_prompt(text_content)
        raw_prompt = self.context.get_raw_vendor_prompt(text_content)

        normalized_task = self.context.normalized_agent.run(norm_prompt)
        raw_task = self.context.raw_agent.run(raw_prompt)

        normalized_result, raw_result = await asyncio.gather(normalized_task, raw_task)

        return normalized_result, raw_result

    async def _update_vendor_config(self, raw_name: str, normalized_name: str) -> None:
        """
        Update vendor configuration with new alias if needed.

        Args:
            raw_name: Raw vendor name from invoice
            normalized_name: Normalized vendor name
        """
        async with self.context.lock:
            vendors_data = load_vendors_data(self.vendors_file)
            updated_data, was_modified = add_or_update_vendor_alias(
                vendors_data, raw_name, normalized_name
            )

            if was_modified:
                save_vendors_data(updated_data, self.vendors_file)

    async def _process_file(
        self,
        source_path: str,
        output_dir: str,
        new_filename: str,
        move_file: bool
    ) -> None:
        """
        Move or copy the processed file to the output directory.

        Args:
            source_path: Original file path
            output_dir: Destination directory
            new_filename: New filename
            move_file: Whether to move or copy
        """
        ensure_directory_exists(output_dir)
        destination_path = os.path.join(output_dir, new_filename)

        if move_file:
            shutil.move(source_path, destination_path)
            logging.info(f"✅ Successfully processed and moved: {new_filename}")
        else:
            shutil.copy(source_path, destination_path)
            logging.info(f"✅ Successfully processed and copied: {new_filename}")
