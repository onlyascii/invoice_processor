"""Configuration management for vendor data."""

import logging
from pathlib import Path
from typing import Dict, List, Any

import yaml

from .utils import sanitize_filename_part


DEFAULT_VENDORS_FILE = "vendors.yaml"


def load_vendors_data(filepath: str = DEFAULT_VENDORS_FILE) -> Dict[str, Any]:
    """
    Load vendor data from a YAML file.

    If the file doesn't exist, it creates one with a default structure to prevent crashes.

    Args:
        filepath: Path to the vendors YAML file

    Returns:
        Dictionary containing vendor data
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

            # Ensure the basic structure is present
            if isinstance(data, dict) and "vendors" in data and isinstance(data["vendors"], list):
                return data

            # If file is empty or malformed, return a default structure
            logging.warning(f"Vendor file '{filepath}' is empty or malformed. Using default structure.")
            return {"vendors": []}

    except FileNotFoundError:
        logging.info(f"Vendor file '{filepath}' not found. Creating a new one.")
        default_data = {"vendors": []}
        save_vendors_data(default_data, filepath)
        return default_data


def save_vendors_data(data: Dict[str, Any], filepath: str = DEFAULT_VENDORS_FILE) -> None:
    """
    Save the vendor data structure back to the YAML file.

    Args:
        data: Vendor data dictionary to save
        filepath: Path to the vendors YAML file
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        logging.info(f"Successfully updated vendor file: {filepath}")
    except Exception as e:
        logging.error(f"Error: Could not write to vendor file. {e}")


def find_vendor_by_name(vendors_data: Dict[str, Any], normalized_name: str) -> Dict[str, Any] | None:
    """
    Find a vendor entry by normalized name.

    Args:
        vendors_data: The vendor data dictionary
        normalized_name: The normalized vendor name to search for

    Returns:
        Vendor dictionary if found, None otherwise
    """
    vendors_list = vendors_data.get("vendors", [])
    simplified_name = sanitize_filename_part(normalized_name).replace('_', ' ').title()

    return next((v for v in vendors_list if v.get("name") == simplified_name), None)


def add_or_update_vendor_alias(
    vendors_data: Dict[str, Any],
    raw_name: str,
    normalized_name: str
) -> tuple[Dict[str, Any], bool]:
    """
    Add or update vendor alias information.

    Args:
        vendors_data: The vendor data dictionary
        raw_name: Raw vendor name from invoice
        normalized_name: Normalized vendor name

    Returns:
        Tuple of (updated_vendors_data, was_modified)
    """
    vendors_list = vendors_data.get("vendors", [])
    was_modified = False

    # Sanitize the normalized name to be used as a primary key
    simplified_name = sanitize_filename_part(normalized_name).replace('_', ' ').title()

    vendor_group = find_vendor_by_name(vendors_data, normalized_name)

    if vendor_group:
        # Existing vendor: check for new aliases
        existing_aliases = [str(alias).lower() for alias in vendor_group.get("aliases", [])]
        if raw_name.lower() not in existing_aliases and raw_name.lower() != simplified_name.lower():
            logging.info(f"Found new alias '{raw_name}' for vendor '{simplified_name}'. Updating config.")
            vendor_group.setdefault("aliases", []).append(raw_name)
            was_modified = True
    else:
        # New vendor: add a new entry
        logging.info(f"Found new vendor '{simplified_name}'. Adding to config.")
        new_vendor = {"name": simplified_name, "aliases": []}

        # Add the raw name as the first alias if it's different
        if raw_name.lower() != simplified_name.lower():
            new_vendor["aliases"].append(raw_name)

        vendors_list.append(new_vendor)
        was_modified = True

    return vendors_data, was_modified
