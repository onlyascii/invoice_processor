"""Utility functions for invoice processing."""

import os
from typing import Optional


def sanitize_filename_part(part: str) -> str:
    """
    Removes characters that are invalid in filenames.

    Args:
        part: The filename part to sanitize

    Returns:
        Sanitized filename part
    """
    # Replace slashes and spaces with underscores
    part = part.replace("/", "_").replace("\\", "_").replace(" ", "_")

    # Define a set of invalid characters for most filesystems
    invalid_chars = set('<>:"|?*')

    # Remove invalid characters
    sanitized_part = "".join(c for c in part if c not in invalid_chars)

    # Remove leading/trailing whitespace, dots, and underscores
    return sanitized_part.strip('._ ')


def ensure_directory_exists(path: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)


def get_pdf_files(folder_path: str) -> list[str]:
    """
    Get all PDF files from a folder.

    Args:
        folder_path: Path to the folder to scan

    Returns:
        List of absolute paths to PDF files
    """
    if not os.path.isdir(folder_path):
        return []

    return [
        os.path.join(folder_path, filename)
        for filename in sorted(os.listdir(folder_path))
        if filename.lower().endswith(".pdf")
    ]


def get_file_basename(file_path: str) -> str:
    """
    Get the basename of a file path.

    Args:
        file_path: Full path to the file

    Returns:
        Base filename
    """
    return os.path.basename(file_path)
