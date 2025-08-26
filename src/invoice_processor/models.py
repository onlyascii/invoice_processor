"""Data models for invoice processing."""

from datetime import date
from pydantic import BaseModel, Field

from .utils import sanitize_filename_part


class RawVendor(BaseModel):
    """Model for raw vendor extraction from invoices."""

    verbatim_vendor_name: str = Field(
        ...,
        description="The exact, verbatim name of the vendor as it appears in the document."
    )


class InvoiceDetails(BaseModel):
    """Model for structured invoice information extraction."""

    vendor: str = Field(
        ...,
        description="A clean, canonical name for the vendor (e.g., 'Amazon Web Services', 'Google', 'Microsoft')."
    )
    invoice_date: date = Field(
        ...,
        description="The date the invoice was issued in YYYY-MM-DD format."
    )
    item_count: int = Field(
        ...,
        description="The total number of distinct items or services listed."
    )
    item_category: str = Field(
        ...,
        description="A brief, general category for the items, e.g., 'books', 'computer hardware', 'software subscription', 'unknown'."
    )
    total_amount: float = Field(
        ...,
        description="The final total amount to be paid."
    )
    total_vat: float = Field(
        0.0,
        description="The total VAT or sales tax amount. If not found, this should be 0.0."
    )

    def to_filename(self) -> str:
        """Formats the extracted details into a sanitized, safe filename string."""
        date_str = self.invoice_date.strftime("%Y%m%d")

        # Sanitize the parts of the filename that can contain special characters
        safe_vendor = sanitize_filename_part(self.vendor)
        safe_category = sanitize_filename_part(self.item_category)

        return (
            f"{safe_vendor}-{date_str}-{self.item_count}-{safe_category}-"
            f"{self.total_amount:.2f}-{self.total_vat:.2f}.pdf"
        )
