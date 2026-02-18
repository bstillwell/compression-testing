#!/usr/bin/env python3

import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import glob
import os

# --- Configuration ---
INPUT_PATTERN = 'results/*.json'
OUTPUT_DIR = 'graphs'

def create_plot(df, x_col, y_col, title, output_path, cpu_model):
    """Generates and saves a specific benchmark plot."""
    plt.figure(figsize=(10, 5))
    sns.set_theme(style="whitegrid")

    # Using sort=False to maintain 'Level' order on the line
    sns.lineplot(
        data=df, x=x_col, y=y_col, hue="Unique_Label",
        style="Unique_Label", markers=True, dashes=False,
        sort=False, linewidth=2, markersize=7, palette="bright"
    )

    plt.title(f"{title}\n{cpu_model}", fontsize=14, pad=15)
    plt.xlabel("Throughput (MiB/s)")
    plt.ylabel("Compression Ratio")

    plt.xlim(left=0)
    plt.ylim(bottom=1)
    plt.legend(title="Algorithm", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    plt.savefig(output_path, dpi=150)
    plt.close()

def process_file(file_path):
    # Load Data
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        return

    # Extract Metadata
    metadata = data.get('metadata', {})
    original_size = metadata.get('original_file_size_bytes', 1)
    cpu_model = metadata.get('cpu_model', 'Unknown CPU')
    file_base = os.path.splitext(os.path.basename(file_path))[0]

    comp_records = []
    decomp_records = []

    # Parse Results
    for res in data.get('results', []):
        version_short = res['version'].split(' ')[-1] if res.get('version') else "?"
        label = f"{res['method']} ({version_short})"
        ratio = original_size / res['compressed_size_bytes']
        level = res['level'] if res['level'] is not None else 0

        # Build Compression dataset
        comp_records.append({
            "Unique_Label": label, "Level": level, "Ratio": ratio,
            "Speed": res.get('compression_throughput_mib_s', 0)
        })

        # Build Decompression dataset
        if 'decompression_throughput_mib_s' in res:
            decomp_records.append({
                "Unique_Label": label, "Level": level, "Ratio": ratio,
                "Speed": res.get('decompression_throughput_mib_s', 0)
            })

    # Generate Compression Graph
    if comp_records:
        df_comp = pd.DataFrame(comp_records).sort_values(by=["Unique_Label", "Level"])
        out_path = os.path.join(OUTPUT_DIR, f"{file_base}_compression.png")
        create_plot(df_comp, "Speed", "Ratio", "Compression", out_path, cpu_model)

    # Generate Decompression Graph
    if decomp_records:
        df_decomp = pd.DataFrame(decomp_records).sort_values(by=["Unique_Label", "Level"])
        out_path = os.path.join(OUTPUT_DIR, f"{file_base}_decompression.png")
        create_plot(df_decomp, "Speed", "Ratio", "Decompression", out_path, cpu_model)

    print(f"Finished processing: {file_base}")

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

    print("\nAll graphs generated in the 'graphs/' directory.")

if __name__ == "__main__":
    main()
