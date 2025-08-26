# Invoice Processor

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
