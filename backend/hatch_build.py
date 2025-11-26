import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class MkinitBuildHook(BuildHookInterface):
    PLUGIN_NAME = "mkinit"

    def initialize(self, version: str, build_data: dict) -> None:
        """Run mkinit to regenerate barrel exports before each build."""
        root = Path(self.root)
        packages = ["shared", "server", "worker"]
        args = ["--recursive", "-i", "--lazy_loader_typed", "--relative"]

        for pkg in packages:
            pkg_path = root / pkg
            if not pkg_path.exists():
                continue

            cmd = ["uvx", "mkinit", pkg] + args
            print(f"[mkinit hook] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=root)
            if result.returncode != 0:
                print(f"[mkinit hook] Failed to generate {pkg}/__init__.py", file=sys.stderr)
                raise SystemExit(result.returncode)

        print("[mkinit hook] Done regenerating __init__.py files")
