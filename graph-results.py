#!/usr/bin/env python3

import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import glob
import os

# --- Configuration ---
# Use glob to find all json files in the results directory
INPUT_PATTERN = 'results/*.json'
OUTPUT_DIR = 'graphs'

def process_file(file_path):
    # 1. Load Data
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        return

    # 2. Prepare DataFrame
    records = []
    # Using .get() for safety in case keys are missing in some files
    metadata = data.get('metadata', {})
    original_size = metadata.get('original_file_size_bytes', 1)
    cpu_model = metadata.get('cpu_model', 'Unknown CPU')

    for res in data.get('results', []):
        version_short = res['version'].split(' ')[-1] if res.get('version') else "?"
        unique_label = f"{res['method']} ({version_short})"

        records.append({
            "Algorithm": res['method'],
            "Unique_Label": unique_label,
            "Level": res['level'] if res['level'] is not None else 0,
            "Ratio": original_size / res['compressed_size_bytes'],
            "Speed": res['compression_throughput_mib_s'],
        })

    if not records:
        print(f"No results found in {file_path}")
        return

    df = pd.DataFrame(records).sort_values(by=["Unique_Label", "Level"])

    # 3. Setup Plot
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 5))

    plot = sns.lineplot(
        data=df, x="Speed", y="Ratio", hue="Unique_Label",
        style="Unique_Label", markers=True, dashes=False,
        sort=False, linewidth=2, markersize=7, palette="bright"
    )

    # 4. Formatting
    file_name = os.path.basename(file_path)
    plt.title(f"Efficiency: {file_name}\nCPU: {cpu_model}", fontsize=14)
    plt.xlabel("Compression Throughput (MiB/s)")
    plt.ylabel("Compression Ratio")
    plt.xlim(left=0)
    plt.ylim(bottom=1)
    plt.legend(title="Algorithm", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    # 5. Save using the original filename but change extension to .png
    output_name = os.path.splitext(file_name)[0] + ".png"
    output_path = os.path.join(OUTPUT_DIR, output_name)
    plt.savefig(output_path, dpi=150)
    plt.close() # Important: Close plot to free memory during loops
    print(f"Processed: {file_name} -> {output_path}")

def main():
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    files = glob.glob(INPUT_PATTERN)

    if not files:
        print(f"No JSON files found in {INPUT_PATTERN}")
        return

    for file in files:
        process_file(file)

if __name__ == "__main__":
    main()
