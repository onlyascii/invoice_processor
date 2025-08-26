import argparse
import yaml
from pydantic import BaseModel, Field
from datetime import date
from pypdf import PdfReader
from enum import Enum
import os
import shutil
import asyncio
from asyncio import Lock

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider

# --- Model for Raw Vendor Extraction ---
class RawVendor(BaseModel):
    verbatim_vendor_name: str = Field(..., description="The exact, verbatim name of the vendor as it appears in the document.")

def load_vendors_data(filepath: str = "vendors.yaml") -> dict:
    """Loads the entire vendor data structure from the YAML file."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f) or {"vendors": []}
    except FileNotFoundError:
        print(f"Warning: Vendor file '{filepath}' not found. Starting with an empty list.")
        return {"vendors": []}

def save_vendors_data(data: dict, filepath: str = "vendors.yaml"):
    """Saves the vendor data structure back to the YAML file."""
    try:
        with open(filepath, 'w') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        print(f"Successfully updated vendor file: {filepath}")
    except Exception as e:
        print(f"Error: Could not write to vendor file. {e}")

async def update_aliases_if_needed(raw_name: str, normalized_name: str, lock: Lock, filepath: str = "vendors.yaml"):
    """
    Atomically checks if a raw vendor name is a new alias and updates the YAML file if so.
    Uses a lock to prevent race conditions during concurrent file access.
    """
    async with lock:
        # This block can only be executed by one task at a time.
        vendors_data = load_vendors_data(filepath)
        is_new_alias = False

        for vendor_group in vendors_data.get("vendors", []):
            if vendor_group.get("name") == normalized_name:
                existing_aliases = [str(a).lower() for a in vendor_group.get("aliases", [])]
                if raw_name.lower() not in existing_aliases and raw_name.lower() != normalized_name.lower():
                    print(f"Found new alias '{raw_name}' for vendor '{normalized_name}'. Updating config.")
                    vendor_group.setdefault("aliases", []).append(raw_name)
                    is_new_alias = True
                break

        if is_new_alias:
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
    try:
        print(f"Starting processing for: {os.path.basename(file_path)}")
        reader = PdfReader(file_path)
        text_content = "".join(page.extract_text() + "\n" for page in reader.pages)
        if not text_content.strip():
            print(f"Could not extract any text from {os.path.basename(file_path)}.")
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
            print(f"Failed to extract normalized details for {os.path.basename(file_path)}.")
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
            print(f"❌ Could not generate filename for {os.path.basename(file_path)} due to incomplete AI response.")
            return

        # --- 4. Move or copy file to output directory ---
        os.makedirs(output_dir, exist_ok=True)
        destination_path = os.path.join(output_dir, new_filename)
        if move_file:
            shutil.move(file_path, destination_path)
            print(f"✅ Successfully processed and moved: {new_filename}")
        else:
            shutil.copy(file_path, destination_path)
            print(f"✅ Successfully processed and copied: {new_filename}")

    except Exception as e:
        print(f"❌ An error occurred while processing {os.path.basename(file_path)}: {e}")

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
    args = parser.parse_args()

    # --- Create shared resources once, including the lock ---
    lock = Lock()
    ollama_model = OpenAIModel(model_name=args.model, provider=OllamaProvider(base_url='http://localhost:11434/v1'))
    normalized_agent = Agent(ollama_model, output_type=InvoiceDetails)
    raw_agent = Agent(ollama_model, output_type=RawVendor)


    if args.file:
        await process_invoice(args.file, args.output_dir, normalized_agent, raw_agent, lock, args.move)
    elif args.folder:
        if not os.path.isdir(args.folder):
            print(f"Error: Folder not found at '{args.folder}'")
            return

        # Create a list of tasks to run concurrently
        tasks = []
        for filename in sorted(os.listdir(args.folder)):
            if filename.lower().endswith(".pdf"):
                file_path = os.path.join(args.folder, filename)
                tasks.append(process_invoice(file_path, args.output_dir, normalized_agent, raw_agent, lock, args.move))

        # Run all tasks concurrently and wait for them to complete
        print(f"--- Found {len(tasks)} PDF files. Processing concurrently... ---")
        await asyncio.gather(*tasks)
        print("\n--- All files processed. ---")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
