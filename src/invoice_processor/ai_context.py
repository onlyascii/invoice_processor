"""AI processing context and agents."""

from asyncio import Lock

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider

from .models import InvoiceDetails, RawVendor


class ProcessingContext:
    """Container for shared resources used during invoice processing."""

    def __init__(self, model_name: str, ollama_url: str):
        """
        Initialize the processing context.

        Args:
            model_name: Name of the AI model to use
            ollama_url: Base URL for the Ollama API
        """
        self.lock = Lock()
        self.ollama_model = OpenAIModel(
            model_name=model_name,
            provider=OllamaProvider(base_url=ollama_url)
        )
        self.normalized_agent = Agent(self.ollama_model, output_type=InvoiceDetails)
        self.raw_agent = Agent(self.ollama_model, output_type=RawVendor)

    def get_normalization_prompt(self, text_content: str) -> str:
        """
        Generate the prompt for invoice detail normalization.

        Args:
            text_content: Extracted text from the invoice PDF

        Returns:
            Formatted prompt string
        """
        return (
            f"From the invoice text below, extract the required information. "
            f"For the vendor, generate a clean, simplified canonical name. For example, if the text says "
            f"'Amazon Business EU S.à.r.l, UK Branch', the canonical name should be 'Amazon Business'.\n\n"
            f"Invoice Text:\n{text_content}"
        )

    def get_raw_vendor_prompt(self, text_content: str) -> str:
        """
        Generate the prompt for raw vendor name extraction.

        Args:
            text_content: Extracted text from the invoice PDF

        Returns:
            Formatted prompt string
        """
        return (
            f"From the following text, extract the exact, verbatim vendor name "
            f"as it appears in the document.\n\n{text_content}"
        )
