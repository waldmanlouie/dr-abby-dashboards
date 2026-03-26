"""Build all Dr Abby dashboards from their Excel source files."""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent

SCRIPTS = [
    'build_trending_dashboard.py',
    'build_growth_dashboard.py',
    'build_projects_dashboard.py',
]


def main():
    print(f"=== Building All Dashboards — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    all_ok = True

    for script in SCRIPTS:
        path = SCRIPT_DIR / script
        print(f"▸ Running {script}...")
        try:
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                print(f"  ✓ {result.stdout.strip()}")
            else:
                print(f"  ✗ FAILED (exit {result.returncode})")
                if result.stderr:
                    print(f"    {result.stderr.strip()}")
                all_ok = False
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            all_ok = False

    print()
    if all_ok:
        print("=== All dashboards built successfully ===")
    else:
        print("=== Some dashboards FAILED — check errors above ===")
        sys.exit(1)


if __name__ == '__main__':
    main()
