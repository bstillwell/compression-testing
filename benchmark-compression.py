#!/usr/bin/env python3

import subprocess
import time
import json
import os
import sys
import platform
import shutil
import argparse
import re

# --- Configuration ---
INPUT_FILENAME = 'silesia.tar'
OUTPUT_JSON = 'compression_benchmark_results.json'
MEBIBYTE = 1024 * 1024

# CLI Tool mapping
COMMANDS = {
    "gzip": "gzip",
    "bzip2": "bzip2",
    "xz": "xz",
    "zstd": "zstd",
    "lz4": "lz4",
    "brotli": "brotli",
    "snappy": "snzip"
}

def get_cpu_model():
    """Returns the CPU model name across different platforms."""
    try:
        if platform.system() == "Windows":
            return subprocess.check_output(["wmic", "cpu", "get", "name"]).decode().strip().split('\n')[1]
        elif platform.system() == "Darwin":
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"

def get_tool_version(name, bin_path):
    """Attempts to get the version string from the CLI tool."""

    # bzip2 hangs on macOS waiting for input if we use the --version flag, so
    # use --help instead
    version_flag = "--help" if name == "bzip2" else "--version"

    try:
        result = subprocess.run(
            [bin_path, version_flag],
            capture_output=True,
            text=True,
            check=False
        )
    except Exception:
        return f"Version Check Failed ({bin_path})"

    # Only grab the first line of the combined stdout/stderr since both are
    # used depending on the tool
    first_line = (result.stdout + result.stderr).splitlines()[0]

    # Define regex patterns for each tool
    patterns = {
        # brotli 1.1.0
        "brotli": r"brotli (\d+\.\d+\.\d+)",

        # bzip2, a block-sorting file compressor.  Version 1.0.8, 13-Jul-2019.
        "bzip2": r"Version (\d+\.\d+\.\d+)",

        # gzip 1.13
        # Apple gzip 475
        "gzip": r"(.*gzip [\d\.]+)",

        # *** LZ4 command line interface 64-bits v1.9.4, by Yann Collet ***
        # *** lz4 v1.10.0 64-bit multithread, by Yann Collet ***
        "lz4": r" v(\d+\.\d+\.\d+)",

        # xz (XZ Utils) 5.8.1
        "xz": r"xz .* (\d+\.\d+\.\d+)",

        # *** zstd command line interface 64-bits v1.4.5, by Yann Collet ***
        # *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***
        "zstd": r" v(\d+\.\d+\.\d+),",
    }

    # Try to extract a clean version number
    if name in patterns:
        match = re.search(patterns[name], first_line)
        if match:
            return match.group(1)

    # Return the first line of output if our matching fails
    return first_line

def run_cli_test(name, bin_path, data, level=None):
    """Runs compression/decompression via CLI pipes."""
    if not shutil.which(bin_path):
        print(f"Skipping {name}: binary '{bin_path}' not found.")
        return None

    # Get version once to use in labeling if testing multiple versions
    version_str = get_tool_version(name, bin_path)

    # Include version in the console label to distinguish multiple zstd versions
    method_label = f"{name} [{version_str.split()[-1]}]" + (f" Lvl {level}" if level is not None else "")

    original_size = len(data)
    size_mib = original_size / MEBIBYTE

    print(f"--> Testing {method_label}...", end='', flush=True)

    # Compression
    if level is not None:
        comp_cmd = [bin_path, "-c", f"-{level}"]

        if name in ["lz4", "xz"]:
            # Make sure these algorithms use a single thread
            comp_cmd.extend(["-T1"])
        elif name == "zstd":
            # Make sure zstd uses a single thread (when version >= 1.1.3)
            zstd_version = tuple(map(int, version_str.split('.')))
            if zstd_version >= (1, 1, 3):
                comp_cmd.extend(["-T1"])

            # Ultra levels are 20-22
            elif level > 19:
                comp_cmd.extend(["--ultra"])
    else:
        print(f"\r\n[Error] No compression level specified")
        return None

    start = time.perf_counter()
    try:
        proc = subprocess.run(comp_cmd, input=data, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"\r\n[Error] {method_label} compression failed.")
        return None
    comp_time = time.perf_counter() - start
    compressed_data = proc.stdout
    compressed_size = len(compressed_data)

    # Decompression
    decomp_cmd = [bin_path, "-d", "-c"]
    start = time.perf_counter()
    try:
        proc = subprocess.run(decomp_cmd, input=compressed_data, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"\r\n[Error] {method_label} decompression failed.")
        return None
    decomp_time = time.perf_counter() - start

    # Validation & Stats
    if len(proc.stdout) != original_size:
        print(f"\r\n[Error] {method_label} integrity check failed!")
        return None

    comp_speed = size_mib / comp_time if comp_time > 0 else 0
    decomp_speed = size_mib / decomp_time if decomp_time > 0 else 0
    ratio = original_size / compressed_size

    print(
        f"\r[Finished] {method_label:<35} | "
        f"Comp: {comp_speed:8.2f} MiB/s | "
        f"Decomp: {decomp_speed:8.2f} MiB/s | "
        f"Ratio: {ratio:5.2f}x"
    )

    return {
        "method": name,
        "level": level,
        "version": version_str,
        "compression_time_seconds": round(comp_time, 4),
        "decompression_time_seconds": round(decomp_time, 4),
        "compression_throughput_mib_s": round(comp_speed, 2),
        "decompression_throughput_mib_s": round(decomp_speed, 2),
        "compressed_size_bytes": compressed_size
    }

def main():
    parser = argparse.ArgumentParser(description="Benchmark compression algorithms using CLI tools.")
    parser.add_argument(
        "--algos",
        type=str,
        help="Comma-separated list of algorithms to test (e.g., gzip,zstd,lz4). Default: all."
    )
    parser.add_argument(
        "--zstd-bins",
        type=str,
        help="Comma-separated list of paths to specific zstd binaries to compare."
    )
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILENAME):
        print(f"Error: {INPUT_FILENAME} not found.")
        return

    if args.algos:
        selected_algos = [a.strip().lower() for a in args.algos.split(',')]
    else:
        selected_algos = list(COMMANDS.keys())

    # Handle multiple Zstd binaries
    zstd_binaries = ["zstd"] # Default
    if args.zstd_bins:
        zstd_binaries = [b.strip() for b in args.zstd_bins.split(',')]

    with open(INPUT_FILENAME, 'rb') as f:
        data = f.read()

    results = []

    # --- Zstandard (Logic adjusted for multiple binaries) ---
    if "zstd" in selected_algos:
        for z_bin in zstd_binaries:
            print(f"\n--- Zstandard (Binary: {z_bin}) ---")

            for l in range(1, 23):
                res = run_cli_test("zstd", z_bin, data, level=l)
                if res: results.append(res)

    # --- Generic Algorithm Loops ---
    standard_loops = [
        ("gzip", "Gzip", range(1, 10)),
        ("bzip2", "Bzip2", range(1, 10)),
        ("xz", "XZ", range(0, 10)),
        ("lz4", "LZ4", range(1, 13)),
        ("brotli", "Brotli", range(1, 12))
    ]

    for key, title, l_range in standard_loops:
        if key in selected_algos:
            print(f"\n--- {title} ---")
            for l in l_range:
                res = run_cli_test(key, COMMANDS[key], data, level=l)
                if res: results.append(res)

    # --- Snappy Logic ---
    if "snappy" in selected_algos:
        print("\n--- Snappy ---")
        res = run_cli_test("snappy", COMMANDS["snappy"], data)
        if res: results.append(res)

    # --- Metadata and Save ---
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "cpu_model": get_cpu_model(),
        "original_file_size_bytes": len(data)
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump({"metadata": metadata, "results": results}, f, indent=4)

    print(f"\nBenchmark complete. Results saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
