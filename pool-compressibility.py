#!/usr/bin/env python3

import rados
import sys
import zlib
import time
import argparse

# Defaults
DEFAULT_POOL = 'default.rgw.buckets.data'
DURATION_SECONDS = 30

# Parse Command Line Arguments
parser = argparse.ArgumentParser(description="Estimate compression savings for a Ceph pool.")
parser.add_argument(
    '-p', '--pool',
    type=str,
    default=DEFAULT_POOL,
    help=f"Name of the pool to check (default: {DEFAULT_POOL})"
)
parser.add_argument(
    '-d', '--duration',
    type=int,
    default=DURATION_SECONDS,
    help=f"Duration in seconds to run the check (default: {DURATION_SECONDS})"
)

args = parser.parse_args()

POOL_NAME = args.pool
DURATION_SECONDS = args.duration

try:
    cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
    cluster.connect()
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

print(f"\nCluster ID: {cluster.get_fsid()}")
print(f"Opening pool: {POOL_NAME}")
print(f"Running compressibility check for {DURATION_SECONDS} seconds...")
print(f"Printing stats every 1 second...\n")

try:
    ioctx = cluster.open_ioctx(POOL_NAME)
except Exception as e:
    print(f"Failed to open pool {POOL_NAME}: {e}")
    cluster.shutdown()
    sys.exit(1)

object_iterator = ioctx.list_objects()

# Stats counters
start_time = time.time()
last_print_time = start_time
objects_checked = 0
total_raw_bytes = 0
total_compressed_bytes = 0

# Fixed column widths
W_ELAPSED = 10
W_OBJECTS = 10
W_DATA = 15
W_RATIO = 12
W_FACTOR = 10

# Print Header
print(f"{'Elapsed':<{W_ELAPSED}} | {'Objects':<{W_OBJECTS}} | {'Data Scanned':<{W_DATA}} | {'Avg Ratio':<{W_RATIO}} | {'Factor':<{W_FACTOR}}")
print("-" * (W_ELAPSED + W_OBJECTS + W_DATA + W_RATIO + W_FACTOR + 12))

while True:
    now = time.time()

    # 1. Check total duration limit
    if now - start_time > DURATION_SECONDS:
        print("\nTime limit reached.")
        break

    # 2. Check if we need to print stats (every 1 second)
    if now - last_print_time >= 1.0:
        elapsed = int(now - start_time)

        # Calculate current running average
        if total_raw_bytes > 0:
            current_ratio = float(total_compressed_bytes) / float(total_raw_bytes)
            # Avoid division by zero
            if total_compressed_bytes > 0:
                current_factor = float(total_raw_bytes) / float(total_compressed_bytes)
            else:
                current_factor = 0.0
        else:
            current_ratio = 1.0
            current_factor = 1.0

        # Format values as strings first to ensure clean padding
        elapsed_str = f"{elapsed}s"
        ratio_str = f"{current_ratio:.2%}"
        factor_str = f"{current_factor:.2f}x"

        # Print Row
        print(f"{elapsed_str:<{W_ELAPSED}} | {objects_checked:<{W_OBJECTS}} | {total_raw_bytes:<{W_DATA}} | {ratio_str:<{W_RATIO}} | {factor_str:<{W_FACTOR}}")

        last_print_time = now

    try:
        obj_entry = next(object_iterator)
        obj_key = obj_entry.key

        try:
            # Read first 4MB (chunks) to estimate compressibility
            data = ioctx.read(obj_key, length=4*1024*1024)
        except rados.ObjectNotFound:
            continue

        if not data:
            continue

        # Calculate compressibility
        raw_len = len(data)
        compressed_data = zlib.compress(data)
        comp_len = len(compressed_data)

        # Update stats
        objects_checked += 1
        total_raw_bytes += raw_len
        total_compressed_bytes += comp_len

    except StopIteration:
        print("\nEnd of pool reached.")
        break
    except Exception as e:
        # Don't crash the script on a single bad object
        continue

# Final Summary
print("\n" + "=" * 30)
print("FINAL SUMMARY")
print("=" * 30)
print(f"Time elapsed: {time.time() - start_time:.2f}s")
print(f"Objects checked: {objects_checked}")

if total_raw_bytes > 0:
    avg_ratio = float(total_compressed_bytes) / float(total_raw_bytes)

    if total_compressed_bytes > 0:
        avg_factor = float(total_raw_bytes) / float(total_compressed_bytes)
    else:
        avg_factor = 0.0

    savings = 100 - (avg_ratio * 100)

    print(f"Total Raw Bytes: {total_raw_bytes}")
    print(f"Global Compression Ratio: {avg_ratio:.2%}")
    print(f"Compression Factor: {avg_factor:.2f}x")
    print(f"Potential Space Savings: {savings:.2f}%")
else:
    print("No data processed.")

ioctx.close()
cluster.shutdown()
