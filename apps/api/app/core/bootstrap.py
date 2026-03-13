from pathlib import Path
import sys


def bootstrap_package_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    packages_root = root / "packages"
    package_roots = []
    if packages_root.exists():
        for candidate in packages_root.iterdir():
            if candidate.is_dir() and (candidate / "pyproject.toml").exists():
                package_roots.append(candidate)
    for package_root in package_roots:
        package_path = str(package_root)
        if package_path not in sys.path:
            sys.path.append(package_path)
