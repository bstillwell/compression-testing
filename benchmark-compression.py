#!/usr/bin/env python3

import subprocess
import time
import json
import os
import sys
import platform
import shutil

# --- Configuration ---
INPUT_FILENAME = 'silesia.tar'
OUTPUT_JSON = 'compression_benchmark_results.json'
MEBIBYTE = 1024 * 1024

# Define the commands. If you have a specific version (e.g., /usr/local/bin/zstd-1.5),
# you can update the path here.
COMMANDS = {
    "gzip": "gzip",
    "bzip2": "bzip2",
    "xz": "xz",
    "zstd": "zstd",
    "lz4": "lz4",
    "snappy": "snzip"  # snzip is the most common CLI for Snappy
}

def get_tool_version(name, bin_path):
    """Attempts to get the version string from the CLI tool."""
    try:
        # Most tools use --version, but some might use -V
        flag = "-V" if name in ["bzip2", "lz4"] else "--version"
        result = subprocess.run([bin_path, flag], capture_output=True, text=True, check=False)
        # Combine stdout and stderr as some tools print version to stderr
        output = (result.stdout + result.stderr).split('\n')[0].strip()
        return output if output else "Unknown Version"
    except Exception:
        return "Version Check Failed"

def run_cli_test(name, bin_path, data, level=None):
    """
    Runs compression and decompression via CLI pipes.
    """
    if not shutil.which(bin_path):
        print(f"Skipping {name}: binary '{bin_path}' not found in PATH.")
        return None

    method_label = f"{name} (Level {level})" if level is not None else name
    original_size = len(data)
    size_mib = original_size / MEBIBYTE

    print(f"--> Testing {method_label}...", end='', flush=True)

    # 1. Compression
    comp_cmd = [bin_path, "-c"] # -c outputs to stdout
    if level is not None:
        comp_cmd.append(f"-{level}")

    start = time.perf_counter()
    proc = subprocess.run(comp_cmd, input=data, capture_output=True, check=True)
    comp_time = time.perf_counter() - start
    compressed_data = proc.stdout
    compressed_size = len(compressed_data)

    # 2. Decompression
    decomp_cmd = [bin_path, "-d", "-c"]
    start = time.perf_counter()
    proc = subprocess.run(decomp_cmd, input=compressed_data, capture_output=True, check=True)
    decomp_time = time.perf_counter() - start

    # 3. Validation
    if len(proc.stdout) != original_size:
        print(f"\r\nError: {name} decompression size mismatch!")
        return None

    # Stats
    comp_speed = size_mib / comp_time if comp_time > 0 else 0
    decomp_speed = size_mib / decomp_time if decomp_time > 0 else 0
    ratio = original_size / compressed_size

    print(
        f"\r[Finished] {method_label:<18} | "
        f"Comp: {comp_speed:8.2f} MiB/s | "
        f"Decomp: {decomp_speed:8.2f} MiB/s | "
        f"Ratio: {ratio:5.2f}x"
    )

    return {
        "method": name,
        "level": level,
        "version": get_tool_version(name, bin_path),
        "compression_time_seconds": round(comp_time, 4),
        "decompression_time_seconds": round(decomp_time, 4),
        "compression_throughput_mib_s": round(comp_speed, 2),
        "decompression_throughput_mib_s": round(decomp_speed, 2),
        "compressed_size_bytes": compressed_size
    }

def main():
    if not os.path.exists(INPUT_FILENAME):
        print(f"Error: {INPUT_FILENAME} not found.")
        return

    with open(INPUT_FILENAME, 'rb') as f:
        data = f.read()

    results = []

    # Benchmark Gzip (1-9)
    print("\n--- Gzip CLI ---")
    for l in range(1, 10):
        res = run_cli_test("gzip", COMMANDS["gzip"], data, level=l)
        if res: results.append(res)

    # Benchmark Bzip2 (1-9)
    print("\n--- Bzip2 CLI ---")
    for l in range(1, 10):
        res = run_cli_test("bzip2", COMMANDS["bzip2"], data, level=l)
        if res: results.append(res)

    # Benchmark XZ (0-9)
    print("\n--- XZ CLI ---")
    for l in range(0, 10):
        res = run_cli_test("xz", COMMANDS["xz"], data, level=l)
        if res: results.append(res)

    # Benchmark Zstd (1-19)
    print("\n--- Zstandard CLI ---")
    for l in range(1, 20):
        res = run_cli_test("zstd", COMMANDS["zstd"], data, level=l)
        if res: results.append(res)

    # Benchmark LZ4 (1-12)
    print("\n--- LZ4 CLI ---")
    for l in range(1, 13):
        res = run_cli_test("lz4", COMMANDS["lz4"], data, level=l)
        if res: results.append(res)

    # Benchmark Snappy (usually snzip)
    print("\n--- Snappy (snzip) CLI ---")
    res = run_cli_test("snappy", COMMANDS["snappy"], data)
    if res: results.append(res)

    # Metadata and Save
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "original_file_size_bytes": len(data)
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump({"metadata": metadata, "results": results}, f, indent=4)

    print(f"\nBenchmark complete. Saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
