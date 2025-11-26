"""Regenerate __init__.py barrel exports for all packages."""

import subprocess
import sys


def main():
    packages = ["shared", "server", "worker"]
    args = ["--recursive", "-i", "--lazy_loader_typed", "--relative"]
    
    for pkg in packages:
        cmd = ["uvx", "mkinit", pkg] + args
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit(result.returncode)
    
    print("Done regenerating __init__.py files")


if __name__ == "__main__":
    main()
