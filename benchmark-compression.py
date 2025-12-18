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
            # Look for the 'model name' line in /proc/cpuinfo
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"

def get_tool_version(name, bin_path):
    """Attempts to get the version string from the CLI tool."""
    try:
        flag = "-V" if name in ["bzip2", "lz4"] else "--version"
        result = subprocess.run([bin_path, flag], capture_output=True, text=True, check=False)
        output = (result.stdout + result.stderr).split('\n')[0].strip()
        return output if output else "Unknown Version"
    except Exception:
        return "Version Check Failed"

def run_cli_test(name, bin_path, data, level=None, extra_args=None):
    """Runs compression/decompression via CLI pipes."""
    if not shutil.which(bin_path):
        print(f"Skipping {name}: binary '{bin_path}' not found.")
        return None

    label_suffix = ""
    if extra_args:
        label_suffix = f" ({' '.join(extra_args)})"
    method_label = f"{name}{label_suffix}" + (f" Lvl {level}" if level is not None else "")

    original_size = len(data)
    size_mib = original_size / MEBIBYTE

    print(f"--> Testing {method_label}...", end='', flush=True)

    # 1. Compression
    comp_cmd = [bin_path, "-c"]
    if extra_args:
        comp_cmd.extend(extra_args)
    if level is not None:
        if name == "brotli":
            comp_cmd.extend(["-q", str(level)])
        else:
            comp_cmd.append(f"-{level}")

    start = time.perf_counter()
    try:
        proc = subprocess.run(comp_cmd, input=data, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"\r\n[Error] {method_label} compression failed.")
        return None
    comp_time = time.perf_counter() - start
    compressed_data = proc.stdout
    compressed_size = len(compressed_data)

    # 2. Decompression
    decomp_cmd = [bin_path, "-d", "-c"]
    start = time.perf_counter()
    try:
        proc = subprocess.run(decomp_cmd, input=compressed_data, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"\r\n[Error] {method_label} decompression failed.")
        return None
    decomp_time = time.perf_counter() - start

    # 3. Validation & Stats
    if len(proc.stdout) != original_size:
        print(f"\r\n[Error] {method_label} integrity check failed!")
        return None

    comp_speed = size_mib / comp_time if comp_time > 0 else 0
    decomp_speed = size_mib / decomp_time if decomp_time > 0 else 0
    ratio = original_size / compressed_size

    print(
        f"\r[Finished] {method_label:<25} | "
        f"Comp: {comp_speed:8.2f} MiB/s | "
        f"Decomp: {decomp_speed:8.2f} MiB/s | "
        f"Ratio: {ratio:5.2f}x"
    )

    return {
        "method": name,
        "level": level,
        "flags": extra_args,
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

    # --- Zstandard (Standard & Ultra) ---
    print("\n--- Zstandard ---")
    for l in range(1, 20):
        res = run_cli_test("zstd", COMMANDS["zstd"], data, level=l)
        if res: results.append(res)
    for l in range(20, 23):
        res = run_cli_test("zstd", COMMANDS["zstd"], data, level=l, extra_args=["--ultra"])
        if res: results.append(res)

    # --- Others ---
    algorithms = [
        ("Gzip", "gzip", range(1, 10)),
        ("Bzip2", "bzip2", range(1, 10)),
        ("XZ", "xz", range(0, 10)),
        ("LZ4", "lz4", range(1, 13)),
        ("Brotli", "brotli", range(1, 12))
    ]

    for title, cmd, l_range in algorithms:
        print(f"\n--- {title} ---")
        for l in l_range:
            res = run_cli_test(cmd, COMMANDS[cmd], data, level=l)
            if res: results.append(res)

    print("\n--- Snappy ---")
    res = run_cli_test("snappy", COMMANDS["snappy"], data)
    if res: results.append(res)

    # --- Save with CPU Metadata ---
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "cpu_model": get_cpu_model(),  # <--- New field
        "python_version": platform.python_version(),
        "original_file_size_bytes": len(data)
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump({"metadata": metadata, "results": results}, f, indent=4)

    print(f"\nBenchmark complete. Results (including CPU: {metadata['cpu_model']}) saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
