"""Memory-tracking wrapper around adk eval.

Tracks: peak RSS, memory delta, open matplotlib figures, GC object growth.
Writes a JSON sidecar file next to the log: <log>.mem.json

Usage: python _mem_wrap.py <adk_path> <eval_args...>
"""
import gc
import json
import os
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path


def measure_subprocess(adk_path, adk_args, log_path):
    """Run adk eval and measure peak memory of THIS process (not subprocess).
    
    Since adk runs in subprocess, we track its peak RSS via /proc/<pid>/status.
    """
    start_time = time.time()
    
    # Start tracemalloc in this script for baseline
    tracemalloc.start()
    gc.collect()
    
    # Open figures before (should be 0)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        figs_before = len(plt.get_fignums())
    except ImportError:
        figs_before = 0
    
    objects_before = len(gc.get_objects())
    
    # Run adk eval as subprocess and watch its memory
    proc = subprocess.Popen(
        [adk_path, "eval"] + adk_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    
    peak_rss_kb = 0
    
    # Poll memory while subprocess runs
    while proc.poll() is None:
        try:
            with open(f"/proc/{proc.pid}/status") as f:
                for line in f:
                    if line.startswith("VmPeak:"):
                        kb = int(line.split()[1])
                        peak_rss_kb = max(peak_rss_kb, kb)
                    elif line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        peak_rss_kb = max(peak_rss_kb, kb)
        except (FileNotFoundError, ProcessLookupError):
            pass
        time.sleep(0.5)
    
    stdout, _ = proc.communicate()
    
    # Write subprocess log
    with open(log_path, "w") as f:
        f.write(stdout)
    
    # Final readings
    gc.collect()
    try:
        figs_after = len(plt.get_fignums())
    except (NameError, ImportError):
        figs_after = 0
    
    objects_after = len(gc.get_objects())
    
    # Compute scores
    peak_mb = peak_rss_kb / 1024 if peak_rss_kb > 0 else 0
    duration_s = time.time() - start_time
    figs_leaked = max(0, figs_after - figs_before)
    objects_delta = objects_after - objects_before
    
    # Leak score logic
    if peak_mb > 2500 or figs_leaked > 2:
        leak_score = "🔴 HIGH"
    elif peak_mb > 2000 or figs_leaked > 0 or objects_delta > 50000:
        leak_score = "🟡 MEDIUM"
    else:
        leak_score = "🟢 LOW"
    
    metrics = {
        "peak_mem_mb": round(peak_mb, 1),
        "open_figures_after": figs_after,
        "figures_leaked": figs_leaked,
        "gc_objects_delta": objects_delta,
        "duration_sec": round(duration_s, 1),
        "leak_score": leak_score,
        "exit_code": proc.returncode,
    }
    
    # Write sidecar JSON
    sidecar = Path(log_path).with_suffix(".mem.json")
    with open(sidecar, "w") as f:
        json.dump(metrics, f, indent=2)
    
    tracemalloc.stop()
    
    print(f"\n=== Memory metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    
    return proc.returncode


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python _mem_wrap.py <adk_path> <log_path> <adk_eval_args...>")
        sys.exit(1)
    
    adk_path = sys.argv[1]
    log_path = sys.argv[2]
    adk_args = sys.argv[3:]
    
    sys.exit(measure_subprocess(adk_path, adk_args, log_path))
