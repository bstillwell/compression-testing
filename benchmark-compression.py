#!/usr/bin/env python3

import time
import json
import os
import sys
import bz2
import lzma
import gzip
import platform
import time

# Attempt to import non-standard libraries
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    print("Warning: 'zstandard' module not found. Skipping zstd tests.")

try:
    import snappy
    HAS_SNAPPY = True
except ImportError:
    HAS_SNAPPY = False
    print("Warning: 'python-snappy' module not found. Skipping snappy tests.")

try:
    import lz4.frame
    import lz4
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False
    print("Warning: 'lz4' module not found. Skipping lz4 tests.")

INPUT_FILENAME = 'silesia.tar'
OUTPUT_JSON = 'compression_benchmark_results.json'

def get_file_content(filename):
    """Reads the entire file into memory to isolate compression performance from Disk I/O."""
    if not os.path.exists(filename):
        print(f"Error: Input file '{filename}' not found.")
        sys.exit(1)

    print(f"Loading {filename} into memory...")
    with open(filename, 'rb') as f:
        return f.read()

def benchmark_algo(name, compress_func, decompress_func, data, version, level=None):
    """
    Generic benchmark function with enhanced reporting.
    (Note: original_size is not included in the returned dictionary)
    """
    method_name = f"{name} (Level {level})" if level is not None else name
    # Print start message, but keep it on one line for better console output
    print(f"--> Testing {method_name}...", end='', flush=True)

    # Compress
    start_time = time.perf_counter()
    try:
        compressed_data = compress_func(data)
    except Exception as e:
        # Clear the line and print error
        print(f"\r\nFailed to compress with {method_name}: {e}")
        return None
    comp_time = time.perf_counter() - start_time
    compressed_size = len(compressed_data)

    # Decompress
    start_time = time.perf_counter()
    try:
        # Check integrity by ensuring decompressed data size is correct
        decompressed_data = decompress_func(compressed_data)
        if len(decompressed_data) != len(data):
            raise RuntimeError("Decompression result size mismatch.")
    except Exception as e:
        # Clear the line and print error
        print(f"\r\nFailed to decompress with {method_name}: {e}")
        return None
    decomp_time = time.perf_counter() - start_time

    # --- ENHANCED REPORTING ---
    original_size = len(data)
    ratio = original_size / compressed_size

    # Print the detailed results over the previous 'Testing...' message
    print(
        f"\r[Finished] {method_name:<18} | "
        f"Comp: {comp_time:8.4f}s | "
        f"Decomp: {decomp_time:8.4f}s | "
        f"Ratio: {ratio:5.2f}x"
    )

    # The returned dictionary no longer includes "original_size_bytes"
    return {
        "method": name,
        "level": level,
        "version": version,
        "compression_time_seconds": round(comp_time, 4),
        "decompression_time_seconds": round(decomp_time, 4),
        "compressed_size_bytes": compressed_size
    }

def main():
    original_data = get_file_content(INPUT_FILENAME)
    results = []

    # ---------------------------------------------------------
    # 1. GZIP (Standard Library)
    # ---------------------------------------------------------
    print("\n--- Benchmarking Gzip ---")
    for level in range(1, 10):
        res = benchmark_algo(
            "gzip",
            lambda d, l=level: gzip.compress(d, compresslevel=l),
            gzip.decompress,
            original_data,
            version=platform.python_version(),
            level=level
        )
        if res: results.append(res)

    # ---------------------------------------------------------
    # 2. BZIP2 (Standard Library)
    # ---------------------------------------------------------
    print("\n--- Benchmarking Bzip2 ---")
    for level in range(1, 10):
        res = benchmark_algo(
            "bzip2",
            lambda d, l=level: bz2.compress(d, compresslevel=l),
            bz2.decompress,
            original_data,
            version=platform.python_version(),
            level=level
        )
        if res: results.append(res)

    # ---------------------------------------------------------
    # 3. XZ / LZMA (Standard Library)
    # ---------------------------------------------------------
    print("\n--- Benchmarking XZ (LZMA) ---")
    for level in range(0, 10):
        res = benchmark_algo(
            "xz",
            lambda d, l=level: lzma.compress(d, preset=l),
            lzma.decompress,
            original_data,
            version=platform.python_version(),
            level=level
        )
        if res: results.append(res)

    # ---------------------------------------------------------
    # 4. ZSTD (External: zstandard)
    # ---------------------------------------------------------
    if HAS_ZSTD:
        print("\n--- Benchmarking Zstandard ---")
        try:
            max_zstd = zstd.MAX_COMPRESSION_LEVEL
            zstd_ver = zstd.ZstdCompressor().version_number
        except:
            max_zstd = 19
            zstd_ver = "unknown"

        for level in range(1, max_zstd + 1):
            def zstd_comp(d, l=level):
                cctx = zstd.ZstdCompressor(level=l)
                return cctx.compress(d)

            def zstd_decomp(d):
                dctx = zstd.ZstdDecompressor()
                return dctx.decompress(d)

            res = benchmark_algo(
                "zstd",
                zstd_comp,
                zstd_decomp,
                original_data,
                version=str(zstd_ver),
                level=level
            )
            if res: results.append(res)

    # ---------------------------------------------------------
    # 5. LZ4 (External: lz4)
    # ---------------------------------------------------------
    if HAS_LZ4:
        print("\n--- Benchmarking LZ4 ---")
        lz4_ver = lz4.library_version_number()
        levels_to_test = list(range(0, 13)) + [16]

        for level in levels_to_test:
             res = benchmark_algo(
                "lz4",
                lambda d, l=level: lz4.frame.compress(d, compression_level=l),
                lz4.frame.decompress,
                original_data,
                version=str(lz4_ver),
                level=level
            )
             if res: results.append(res)

    # ---------------------------------------------------------
    # 6. Snappy (External: python-snappy)
    # ---------------------------------------------------------
    if HAS_SNAPPY:
        print("\n--- Benchmarking Snappy ---")
        try:
            snappy_ver = snappy.__version__
        except:
            snappy_ver = "unknown"

        res = benchmark_algo(
            "snappy",
            snappy.compress,
            snappy.uncompress,
            original_data,
            version=str(snappy_ver),
            level="default"
        )
        if res: results.append(res)

    # ---------------------------------------------------------
    # Save Results
    # ---------------------------------------------------------
    print(f"\nWriting results to {OUTPUT_JSON}...")

    # original_size_bytes is now explicitly defined in metadata
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "original_file_size_bytes": len(original_data)
    }

    final_output = {
        "metadata": metadata,
        "results": results
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(final_output, f, indent=4)

    print("\nBenchmark complete. Results saved to", OUTPUT_JSON)

if __name__ == "__main__":
    main()
