# Invoice Processor

An AI-powered invoice processing and organization system that automatically extracts information from PDF invoices and organizes them with structured filenames.

## Features

- **AI-Powered Extraction**: Uses local AI models via Ollama to extract vendor details, dates, amounts, and categories
- **Smart Vendor Management**: Automatically maintains vendor aliases and canonical names in YAML configuration
- **Concurrent Processing**: Processes multiple invoices simultaneously for better performance
- **Interactive TUI**: Beautiful terminal user interface built with Textual
- **CLI Support**: Full command-line interface for automated workflows
- **System Monitoring**: Real-time CPU, memory, and GPU monitoring
- **Flexible Output**: Copy or move processed files with structured naming

## Installation

```bash
# Install with uv (recommended)
uv install

# Or install with pip in editable mode
pip install -e .

# Optional: Install GPU monitoring support
pip install -e .[gpu]
```

## Usage

### Multiple Ways to Run

The application can be run in several ways:

#### 1. As a Python Module (Recommended)
```bash
# Process a single file
python -m src.invoice_processor --file invoice.pdf

# Process all PDFs in a folder
python -m src.invoice_processor --folder /path/to/invoices

# Use interactive TUI mode
python -m src.invoice_processor --folder /path/to/invoices --tui

# Move files instead of copying
python -m src.invoice_processor --folder /path/to/invoices --move

# Custom model and output directory
python -m src.invoice_processor --folder /path/to/invoices --model qwen3 --output-dir processed
```

#### 2. Standalone Script
```bash
# For environments where module import might have issues
python run.py --folder /path/to/invoices --tui
```

#### 3. Package Entry Point (After Installation)
```bash
# After running pip install -e .
invoice-processor --folder /path/to/invoices --tui
```

#### 4. Legacy Compatibility
```bash
# Original main.py for backward compatibility
python main.py --folder /path/to/invoices --tui
```

## Project Structure

```
src/invoice_processor/
├── __init__.py              # Package initialization
├── models.py                # Pydantic data models
├── utils.py                 # Utility functions
├── config.py                # Configuration management
├── ai_context.py           # AI processing context
├── processor.py            # Core invoice processing
├── monitoring.py           # System resource monitoring
├── cli.py                  # Command line interface
└── tui/                    # Terminal UI components
    ├── __init__.py
    ├── app.py              # Main TUI application
    └── logging_handler.py  # Custom logging for TUI
```

## Architecture

The system follows modern Python best practices with clear separation of concerns:

### Core Components

- **Models**: Pydantic models for data validation and structured output
- **Processor**: Core business logic for invoice processing
- **AI Context**: Manages AI model interactions and prompt generation
- **Config**: YAML-based vendor configuration management
- **Utils**: Shared utility functions
- **Monitoring**: System resource monitoring

### User Interfaces

- **CLI**: Full-featured command-line interface with comprehensive options
- **TUI**: Interactive terminal UI with real-time progress and system monitoring

## Configuration

The system uses a `vendors.yaml` file to maintain vendor information:

```yaml
vendors:
  - name: "Amazon Business"
    aliases:
      - "Amazon Business EU S.à.r.l"
      - "Amazon Business UK"
  - name: "Microsoft"
    aliases:
      - "Microsoft Corporation"
      - "Microsoft Ireland Operations Limited"
```

This file is automatically updated as new vendors are discovered.

## Output Format

Processed invoices are renamed with a structured format:

```
{vendor}-{date}-{item_count}-{category}-{total}-{vat}.pdf
```

Example: `Amazon_Business-20250225-2-computer_hardware-100.00-20.00.pdf`

## Development

### Running Tests

```bash
# Run with the configured Python environment
python -m pytest
```

### Code Quality

The codebase follows modern Python standards:

- Type hints throughout
- Comprehensive docstrings
- Modular architecture
- Async/await for concurrent operations
- Error handling and logging
- Configuration management

### Adding New Features

The modular structure makes it easy to extend:

1. Add new models to `models.py`
2. Extend processing logic in `processor.py`
3. Add UI components in the `tui/` package
4. Update CLI options in `cli.py`

## Requirements

- Python 3.13+
- Ollama running locally (default: http://localhost:11434)
- AI model (default: qwen3)

## License

See LICENSE file for details.

A script to intelligently process and rename PDF invoices using a local AI model.

## Description

This tool automates the processing of PDF invoices. It uses an AI model (via Ollama) to extract key information like the vendor, invoice date, item details, and total amounts. Based on this extracted data, it renames the invoice files into a clean, standardized format.

A key feature is its ability to learn and manage vendor names. It maintains a `vendors.yaml` file, automatically creating canonical vendor names and mapping verbatim names from invoices as aliases. This ensures consistent naming across all your documents.

## Features

- Extracts structured data from PDF invoices using a local AI model.
- Intelligently renames files based on extracted content (Vendor, Date, Item Count, Category, Amount).
- Automatically learns and catalogs vendor names and their aliases in `vendors.yaml`.
- Processes a single file or an entire folder of invoices concurrently.
- Can move or copy processed files to a designated output directory.
- Logs processing activity and performance metrics for both individual files and the total run.
- **Interactive TUI Mode**: A modern terminal user interface for visual file selection and real-time processing monitoring.
- Simple and flexible command-line interface.

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- A running [Ollama](https://ollama.com/) instance with a model (e.g., `qwen2`, `llama3`).
- [Textual](https://textual.textualize.io/) (included in dependencies for TUI functionality).

### Installation

1.  Clone the repository:
    ```sh
    git clone https://github.com/onlyascii/invoice_processor.git
    ```
2.  Navigate to the project directory:
    ```sh
    cd invoice_processor
    ```
3.  Create a virtual environment and install dependencies:
    ```sh
    uv sync
    ```

## Usage

The script can process a single file or all PDF files in a directory. To run the script, use the `uv run` command, which executes commands within the project's managed virtual environment.

### Interactive TUI Mode (Recommended)

For folder processing, you can use the interactive Terminal User Interface (TUI) mode, which provides a visual interface for selecting files and monitoring processing progress:

```sh
uv run main.py --folder path/to/invoices_to_process --tui --output-dir processed
```

**TUI Features:**
- **File Selection**: Browse and select specific PDF files to process using spacebar
- **Real-time Logging**: View processing logs and AI model responses in real-time
- **Progress Monitoring**: Track processing progress with a visual progress bar
- **System Monitoring**: Monitor CPU, memory, and GPU usage during processing
- **Interactive Controls**:
  - `Space` - Toggle file selection
  - `p` - Process selected files
  - `r` - Refresh file list
  - `q` - Quit application

### Process a single invoice

```sh
uv run main.py --file path/to/your/invoice.pdf --output-dir processed
```

### Process all invoices in a folder (CLI mode)

This will process all `.pdf` files in the `invoices_to_process` directory concurrently.

```sh
uv run main.py --folder path/to/invoices_to_process --output-dir processed
```

### Command-Line Arguments

-   `--file <path>`: Path to a single PDF file to process.
-   `--folder <path>`: Path to a folder containing PDF files to process.
-   `--output-dir <path>`: The directory to save renamed files. Defaults to `processed_invoices`.
-   `--model <model_name>`: The Ollama model to use. Defaults to `qwen2`.
-   `--move`: Move processed files to the output directory instead of copying them.
-   `--tui`: Enable interactive Terminal User Interface for folder processing. Only available with `--folder`.
-   `--log-file <path>`: Path for the main processing log. Defaults to `processing_log.txt`.
-   `--args-log-file <path>`: Path for a JSON log of script arguments and performance, including the number of files processed. Disabled by default.

### TUI Mode vs CLI Mode

- **TUI Mode** (`--tui`): Interactive interface with file selection, real-time logs, and system monitoring. Best for selective processing and monitoring.
- **CLI Mode** (default): Processes all files automatically with console output. Best for batch processing and automation.

## Contributing

Contributions are welcome. Please feel free to open an issue or submit a pull request.

## License

This project is licensed under the Apache 2.0 License. See the `LICENSE` file for more details.
