import argparse
import yaml
from pydantic import BaseModel, Field
from datetime import date
from pypdf import PdfReader
from enum import Enum
import os
import shutil

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

def update_aliases_if_needed(raw_name: str, normalized_name: str, filepath: str = "vendors.yaml"):
    """Checks if a raw vendor name is a new alias and updates the YAML file if so."""
    vendors_data = load_vendors_data(filepath)
    is_new_alias = False

    for vendor_group in vendors_data.get("vendors", []):
        if vendor_group.get("name") == normalized_name:
            # Check if the raw name is already in the aliases (case-insensitive)
            existing_aliases = [str(a).lower() for a in vendor_group.get("aliases", [])]
            if raw_name.lower() not in existing_aliases and raw_name.lower() != normalized_name.lower():
                print(f"Found new alias '{raw_name}' for vendor '{normalized_name}'.")
                vendor_group.setdefault("aliases", []).append(raw_name)
                is_new_alias = True
            break # Found the correct vendor group

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

def process_invoice(file_path: str, model: str, output_dir: str) -> None:
    try:
        reader = PdfReader(file_path)
        text_content = "".join(page.extract_text() + "\n" for page in reader.pages)
        if not text_content.strip():
            print("Could not extract any text from the PDF.")
            return

        ollama_model = OpenAIModel(model_name=model, provider=OllamaProvider(base_url='http://localhost:11434/v1'))

        # --- 1. First Pass: Normalize and Extract Details ---
        print("\n--- Pass 1: Normalizing invoice details ---")
        norm_prompt = (
            f"From the invoice text below, extract the required information. "
            f"For the vendor, you must choose one of the following canonical names: {canonical_vendor_names}. "
            f"Map the vendor found in the text to the most appropriate name from that list.\n\n"
            f"Invoice Text:\n{text_content}"
        )
        normalized_agent = Agent(ollama_model, output_type=InvoiceDetails)
        normalized_result = normalized_agent.run_sync(norm_prompt)

        if not normalized_result:
            print("Failed to extract normalized invoice details.")
            return

        # --- 2. Second Pass: Extract Raw Vendor Name ---
        print("\n--- Pass 2: Extracting verbatim vendor name ---")
        raw_prompt = f"From the following text, extract the exact, verbatim vendor name as it appears in the document.\n\n{text_content}"
        raw_agent = Agent(ollama_model, output_type=RawVendor)
        raw_result = raw_agent.run_sync(raw_prompt)

        # --- 3. Compare and Update YAML ---
        if raw_result:
            update_aliases_if_needed(
                raw_name=raw_result.output.verbatim_vendor_name,
                normalized_name=normalized_result.output.vendor.value
            )

        new_filename = normalized_result.output.to_filename()
        print(f"\n--- Generated Filename (AI Normalized) ---")
        print(new_filename)

        # --- 4. Copy file to output directory ---
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Construct the full destination path
        destination_path = os.path.join(output_dir, new_filename)

        # Copy the original file to the new destination with the new name
        shutil.copy(file_path, destination_path)
        print(f"\nSuccessfully copied and renamed invoice to:\n{destination_path}")

    except Exception as e:
        print(f"An error occurred while processing {os.path.basename(file_path)}: {e}")

def main():
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
    args = parser.parse_args()

    if args.file:
        # Process a single file
        print(f"--- Processing single file: {args.file} ---")
        process_invoice(args.file, args.model, args.output_dir)
    elif args.folder:
        # Process a whole folder
        print(f"--- Processing folder: {args.folder} ---")
        if not os.path.isdir(args.folder):
            print(f"Error: Folder not found at '{args.folder}'")
            return

        for filename in sorted(os.listdir(args.folder)):
            if filename.lower().endswith(".pdf"):
                file_path = os.path.join(args.folder, filename)
                print(f"\n----------------------------------\n>>> Processing: {file_path} <<<")
                process_invoice(file_path, args.model, args.output_dir)
            else:
                print(f"Skipping non-PDF file: {filename}")

if __name__ == "__main__":
    main()
