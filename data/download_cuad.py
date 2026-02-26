"""
download_cuad.py - Download real contracts from the CUAD dataset

CUAD (Contract Understanding Atticus Dataset) contains 510 real commercial contracts
annotated with 41 types of legal clauses. It's completely free and open access.

Run this script to download 5 real contracts to use with the system.
"""

import os
import json

def download_cuad_sample():
    """Download sample contracts from CUAD dataset via HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets library...")
        os.system("pip install datasets --break-system-packages")
        from datasets import load_dataset

    print("Downloading CUAD dataset (this may take a minute)...")
    ds = load_dataset("theatticusproject/cuad", split="test", streaming=True)

    output_dir = "data/sample_contracts"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for item in ds:
        if count >= 5:
            break

        # Each item has 'context' (full contract text) and metadata
        filename = item.get("id", f"contract_{count}").replace("/", "_")
        filepath = os.path.join(output_dir, f"cuad_{filename}.txt")

        contract_text = item.get("context", "")
        if len(contract_text) < 500:
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contract_text)

        print(f"✓ Saved: {filepath} ({len(contract_text)} chars)")
        count += 1

    print(f"\n✓ Downloaded {count} real CUAD contracts to {output_dir}/")
    print("Upload them through the web UI at http://localhost:3000")


if __name__ == "__main__":
    download_cuad_sample()
