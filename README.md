# Invoice Processor

A simple project to process invoices from various formats.

## Description

This tool is designed to automate the extraction of data from invoice documents. It can parse files like PDFs and images, pull out key information such as invoice number, date, total amount, and vendor details, and then save the extracted data into a structured format like CSV or JSON.

## Features

- Extracts data from PDF, PNG, and JPG files.
- Validates key invoice fields.
- Exports extracted data to CSV or JSON.
- Simple command-line interface.

## Getting Started

### Prerequisites

- Python 3.13+
- uv

### Installation

1.  Clone the repository:
    ```sh
    git clone https://github.com/your-username/invoice_processor.git
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

To process an invoice, run the main script from your terminal:

```sh
python main.py --input path/to/invoice.pdf --output output.csv
```

## Contributing

Contributions are welcome. Please feel free to open an issue or submit a pull request.

## License

This project is licensed under the Apache 2.0 License. See the `LICENSE` file for more details.
