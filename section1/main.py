print(">>> main.py loaded")

import os
import subprocess
import sys
from datetime import datetime

print(">>> imports done")

SECTION_DIR = "section1"

PIPELINE = [
    ("Fetch FRED", "fetch_fred.py"),
    ("Fetch BLS", "fetch_bls.py"),
    ("Fetch BEA", "fetch_bea.py"),
    ("Fetch Global", "fetch_global.py"),
    ("Aggregate sources", "aggregate.py"),
    ("Consolidate for LLM", "consolidate.py"),
    ("Write narrative", "ai_writer.py"),
    ("Build charts", "build_charts.py"),
    ("Build email", "build_email.py"),
]


def run_step(label, script):
    print("")
    print("=" * 60)
    print(">>> " + label + " (" + script + ")")
    print("=" * 60)

    script_path = os.path.join(SECTION_DIR, script)
    if not os.path.exists(script_path):
        print(">>> ERROR: " + script_path + " not found.")
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-u", script_path],
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(">>> TIMEOUT: " + script + " exceeded 300 seconds")
        return False
    except Exception as e:
        print(">>> EXCEPTION running " + script + ": " + str(e))
        return False

    if result.returncode != 0:
        print(">>> " + script + " exited with code " + str(result.returncode))
        return False

    print(">>> " + script + " OK")
    return True


def main():
    print(">>> main block entered")
    started = datetime.now()
    print(">>> pipeline started at " + started.isoformat())

    results = []
    for label, script in PIPELINE:
        ok = run_step(label, script)
        results.append((script, ok))

    finished = datetime.now()
    duration = (finished - started).total_seconds()

    print("")
    print("=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for script, ok in results:
        status = "OK" if ok else "FAILED"
        print("  " + status + " - " + script)
    print("")
    print("Duration: " + str(round(duration, 1)) + " seconds")

    all_ok = all(ok for _, ok in results)
    if all_ok:
        print(">>> PIPELINE COMPLETE")
    else:
        print(">>> PIPELINE COMPLETED WITH FAILURES")
        failed = [s for s, ok in results if not ok]
        print(">>> Failed steps: " + str(failed))

    print(">>> DONE")


if __name__ == "__main__":
    main()
