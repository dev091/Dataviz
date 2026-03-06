from pathlib import Path
import sys


def bootstrap_package_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    package_roots = [
        root / "packages" / "connectors",
        root / "packages" / "semantic",
        root / "packages" / "analytics",
    ]
    for package_root in package_roots:
        package_path = str(package_root)
        if package_path not in sys.path:
            sys.path.append(package_path)
