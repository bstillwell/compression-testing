#!/usr/bin/env python3

import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# --- Configuration ---
INPUT_JSON = 'compression_benchmark_results.json'
OUTPUT_IMAGE = 'benchmark_linear_lines.png'

def main():
    # 1. Load Data
    try:
        with open(INPUT_JSON, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_JSON} not found. Run the benchmark first.")
        return

    # 2. Prepare DataFrame
    records = []
    original_size = data['metadata']['original_file_size_bytes']
    cpu_model = data['metadata'].get('cpu_model', 'Unknown CPU')

    for res in data['results']:
        version_short = res['version'].split(' ')[-1] if res['version'] else "?"
        unique_label = f"{res['method']} ({version_short})"

        records.append({
            "Algorithm": res['method'],
            "Unique_Label": unique_label,
            "Level": res['level'] if res['level'] is not None else 0,
            "Ratio": original_size / res['compressed_size_bytes'],
            "Speed": res['compression_throughput_mib_s'],
        })

    df = pd.DataFrame(records)

    # 3. Sort for logical line drawing (Level 1 -> 2 -> 3...)
    df = df.sort_values(by=["Unique_Label", "Level"])

    # 4. Setup Plot
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 5))

    # 5. Create Line Plot
    # - linear scale (default)
    # - sort=False ensures lines follow 'Level' order, not 'Speed' order
    # - markers=True adds dots at each data point without labels
    plot = sns.lineplot(
        data=df,
        x="Speed",
        y="Ratio",
        hue="Unique_Label",
        style="Unique_Label",
        markers=True,
        dashes=False,
        sort=False,
        linewidth=2,
        markersize=7,
        palette="bright"
    )

    # 6. Formatting
    plt.title(f"Compression Efficiency: Speed vs. Ratio (Linear Scale)\nCPU: {cpu_model}", fontsize=15, pad=20)
    plt.xlabel("Compression Throughput (MiB/s)", fontsize=12)
    plt.ylabel("Compression Ratio", fontsize=12)

    plt.xlim(left=0)
    plt.ylim(bottom=1)

    # Legend placement
    plt.legend(title="Algorithm (Version)", bbox_to_anchor=(1.01, 1), loc='upper left')

    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=150)
    print(f"Graph saved to {OUTPUT_IMAGE}")

if __name__ == "__main__":
    main()
