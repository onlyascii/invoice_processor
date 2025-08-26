import argparse
import json
import yaml
from pydantic import BaseModel, Field
from datetime import date, datetime
from pypdf import PdfReader
from enum import Enum
import os
import shutil
import asyncio
from asyncio import Lock
import time
import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider

# --- Model for Raw Vendor Extraction ---
class RawVendor(BaseModel):
    verbatim_vendor_name: str = Field(..., description="The exact, verbatim name of the vendor as it appears in the document.")

def load_vendors_data(filepath: str = "vendors.yaml") -> dict:
    """
    Loads vendor data from a YAML file. If the file doesn't exist, it creates one
    with a default structure to prevent crashes.
    """
    try:
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
            # Ensure the basic structure is present
            if isinstance(data, dict) and "vendors" in data and isinstance(data["vendors"], list):
                return data
            # If file is empty or malformed, return a default structure
            print(f"Warning: Vendor file '{filepath}' is empty or malformed. Using default structure.")
            return {"vendors": []}
    except FileNotFoundError:
        print(f"Info: Vendor file '{filepath}' not found. Creating a new one.")
        default_data = {"vendors": []}
        save_vendors_data(default_data, filepath)
        return default_data

def save_vendors_data(data: dict, filepath: str = "vendors.yaml"):
    """Saves the vendor data structure back to the YAML file."""
    try:
        with open(filepath, 'w') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        logging.info(f"Successfully updated vendor file: {filepath}")
    except Exception as e:
        logging.error(f"Error: Could not write to vendor file. {e}")

async def update_aliases_if_needed(raw_name: str, normalized_name: str, lock: Lock, filepath: str = "vendors.yaml"):
    """
    Atomically updates the vendor file. If the normalized vendor exists, it adds a new alias.
    If the normalized vendor does not exist, it creates a new vendor entry.
    Uses a lock to prevent race conditions during concurrent file access.
    """
    async with lock:
        vendors_data = load_vendors_data(filepath)
        vendors_list = vendors_data.get("vendors", [])
        file_was_modified = False

        # Sanitize the normalized name to be used as a primary key
        simplified_name = sanitize_filename_part(normalized_name).replace('_', ' ').title()

        vendor_group = next((v for v in vendors_list if v.get("name") == simplified_name), None)

        if vendor_group:
            # Existing vendor: check for new aliases
            existing_aliases = [str(a).lower() for a in vendor_group.get("aliases", [])]
            if raw_name.lower() not in existing_aliases and raw_name.lower() != simplified_name.lower():
                logging.info(f"Found new alias '{raw_name}' for vendor '{simplified_name}'. Updating config.")
                vendor_group.setdefault("aliases", []).append(raw_name)
                file_was_modified = True
        else:
            # New vendor: add a new entry
            logging.info(f"Found new vendor '{simplified_name}'. Adding to config.")
            new_vendor = {"name": simplified_name, "aliases": []}
            # Add the raw name as the first alias if it's different
            if raw_name.lower() != simplified_name.lower():
                new_vendor["aliases"].append(raw_name)
            vendors_list.append(new_vendor)
            file_was_modified = True

        if file_was_modified:
            save_vendors_data(vendors_data, filepath)

def sanitize_filename_part(part: str) -> str:
    """Removes characters that are invalid in filenames."""
    # Replace slashes and spaces with underscores
    part = part.replace("/", "_").replace("\\", "_").replace(" ", "_")
    # Define a set of invalid characters for most filesystems
    invalid_chars = set('<>:"|?*')
    # Remove invalid characters
    sanitized_part = "".join(c for c in part if c not in invalid_chars)
    # Remove leading/trailing whitespace, dots, and underscores
    return sanitized_part.strip('._ ')

# --- Dynamic Enum and Pydantic Models ---
vendors_data = load_vendors_data()
canonical_vendor_names = [v.get("name") for v in vendors_data.get("vendors", []) if v.get("name")]
if not canonical_vendor_names:
    canonical_vendor_names = ["Unknown"]
VendorEnum = Enum("VendorEnum", {name: name for name in canonical_vendor_names})

class InvoiceDetails(BaseModel):
    vendor: VendorEnum = Field(..., description="The canonical vendor name, chosen from the provided list.")
    invoice_date: date = Field(..., description="The date the invoice was issued in YYYY-MM-DD format.")
    item_count: int = Field(..., description="The total number of distinct items or services listed.")
    item_category: str = Field(..., description="A brief, general category for the items, e.g., 'books', 'computer hardware', 'software subscription', 'unknown'.")
    total_amount: float = Field(..., description="The final total amount to be paid.")
    total_vat: float = Field(0.0, description="The total VAT or sales tax amount. If not found, this should be 0.0.")

    def to_filename(self) -> str:
        """Formats the extracted details into a sanitized, safe filename string."""
        date_str = self.invoice_date.strftime("%Y%m%d")

        # Sanitize the parts of the filename that can contain special characters
        safe_vendor = sanitize_filename_part(self.vendor.value)
        safe_category = sanitize_filename_part(self.item_category)

        return f"{safe_vendor}-{date_str}-{self.item_count}-{safe_category}-{self.total_amount:.2f}-{self.total_vat:.2f}.pdf"

async def process_invoice(file_path: str, output_dir: str, normalized_agent: Agent[None, InvoiceDetails], raw_agent: Agent[None, RawVendor], lock: Lock, move_file: bool = False) -> None:
    """Asynchronously processes a single PDF file using shared agents and a file lock."""
    start_time = time.time()
    try:
        logging.info(f"Starting processing for: {os.path.basename(file_path)}")
        reader = PdfReader(file_path)
        text_content = "".join(page.extract_text() + "\n" for page in reader.pages)
        if not text_content.strip():
            logging.warning(f"Could not extract any text from {os.path.basename(file_path)}.")
            return

        # Agents are now passed in, so we don't create them here.

        # --- 1. First Pass: Normalize and Extract Details (Async) ---
        norm_prompt = (
            f"From the invoice text below, extract the required information. "
            f"For the vendor, you must choose one of the following canonical names: {canonical_vendor_names}. "
            f"Map the vendor found in the text to the most appropriate name from that list.\n\n"
            f"Invoice Text:\n{text_content}"
        )
        normalized_result = await normalized_agent.run(norm_prompt)

        if not normalized_result:
            logging.error(f"Failed to extract normalized details for {os.path.basename(file_path)}.")
            return

        # --- 2. Second Pass: Extract Raw Vendor Name (Async) ---
        raw_prompt = f"From the following text, extract the exact, verbatim vendor name as it appears in the document.\n\n{text_content}"
        raw_result = await raw_agent.run(raw_prompt)

        # --- 3. Compare and Update YAML (Atomically) ---
        # Robustly check if both AI calls were successful before proceeding
        if raw_result and raw_result.output and normalized_result and normalized_result.output:
            await update_aliases_if_needed(
                raw_name=raw_result.output.verbatim_vendor_name,
                normalized_name=normalized_result.output.vendor.value,
                lock=lock
            )
            new_filename = normalized_result.output.to_filename()
        else:
            logging.error(f"❌ Could not generate filename for {os.path.basename(file_path)} due to incomplete AI response.")
            return

        # --- 4. Move or copy file to output directory ---
        os.makedirs(output_dir, exist_ok=True)
        destination_path = os.path.join(output_dir, new_filename)
        if move_file:
            shutil.move(file_path, destination_path)
            logging.info(f"✅ Successfully processed and moved: {new_filename}")
        else:
            shutil.copy(file_path, destination_path)
            logging.info(f"✅ Successfully processed and copied: {new_filename}")

    except Exception as e:
        logging.error(f"❌ An error occurred while processing {os.path.basename(file_path)}: {e}")
    finally:
        duration = time.time() - start_time
        logging.info(f"Finished processing {os.path.basename(file_path)} in {duration:.2f} seconds.")


async def main():
    parser = argparse.ArgumentParser(description="Extracts invoice data from PDF files and renames them.")

    # Create a mutually exclusive group. One of these arguments is required.
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="The path to a single PDF file to be processed.")
    group.add_argument("--folder", type=str, help="The path to a folder containing PDF files to be processed.")

    parser.add_argument("--model", type=str, default="qwen3", help="The model to use for processing.")
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
    args = parser.parse_args()

    # --- Setup Logging ---
    # Remove all handlers associated with the root logger object to avoid conflicts.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging to write to a file and the console.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        filename=args.log_file,
        filemode='a'  # Append to the log file on each run
    )
    # Add a handler to also print log messages to the console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s')) # Console logs are simpler
    logging.getLogger().addHandler(console_handler)

    total_start_time = time.time()

    # --- Create shared resources once, including the lock ---
    lock = Lock()
    ollama_model = OpenAIModel(model_name=args.model, provider=OllamaProvider(base_url='http://localhost:11434/v1'))
    normalized_agent = Agent(ollama_model, output_type=InvoiceDetails)
    raw_agent = Agent(ollama_model, output_type=RawVendor)


    if args.file:
        await process_invoice(args.file, args.output_dir, normalized_agent, raw_agent, lock, args.move)
    elif args.folder:
        if not os.path.isdir(args.folder):
            logging.error(f"Error: Folder not found at '{args.folder}'")
            return

        # Create a list of tasks to run concurrently
        tasks = []
        for filename in sorted(os.listdir(args.folder)):
            if filename.lower().endswith(".pdf"):
                file_path = os.path.join(args.folder, filename)
                tasks.append(process_invoice(file_path, args.output_dir, normalized_agent, raw_agent, lock, args.move))

        # Run all tasks concurrently and wait for them to complete
        logging.info(f"--- Found {len(tasks)} PDF files. Processing concurrently... ---")
        await asyncio.gather(*tasks)
        logging.info("\n--- All files processed. ---")

    total_duration = time.time() - total_start_time
    logging.info(f"--- Total execution time: {total_duration:.2f} seconds ---")

    # --- Log arguments and performance to a separate file if requested ---
    if args.args_log_file:
        try:
            run_info = {
                "timestamp": datetime.now().isoformat(),
                "arguments": vars(args),
                "total_duration_seconds": round(total_duration, 2)
            }
            with open(args.args_log_file, 'a') as f:
                f.write(json.dumps(run_info) + '\n')
        except Exception as e:
            logging.error(f"Error: Could not write to arguments log file: {e}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
