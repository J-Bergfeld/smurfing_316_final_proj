"""Run a locally configured competitor lineup with pinned checkouts."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "competitors" / "lineup.json"


def fetch(repo, revision, cache):
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / repo.replace("/", "--")
    if not dest.exists():
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            checkout = Path(temp) / "checkout"
            subprocess.run(["git", "init", "-q", str(checkout)], check=True)
            subprocess.run(["git", "-C", str(checkout), "fetch", "-q", "--depth=1",
                            "https://github.com/" + repo + ".git", revision], check=True)
            subprocess.run(["git", "-C", str(checkout), "checkout", "-q", "--detach", revision],
                           check=True)
            checkout.rename(dest)
    actual = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision:
        raise RuntimeError(f"{dest} is at {actual}, expected pinned revision {revision}")
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Ignored local lineup JSON (default: competitors/lineup.json).")
    parser.add_argument("--seed", type=int, default=420000)
    parser.add_argument("--opponents-dir", type=Path, help="Use checkouts from this directory without fetching.")
    parser.add_argument("--fetch-only", action="store_true", help="Download the pinned opponents without running a match.")
    parser.add_argument("--trace", type=Path, help="Write subject observations and actions to a JSONL file.")
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    if not config_path.is_file():
        parser.error(f"Missing local lineup: {config_path}; see docs/local-simulator.md")
    try:
        config = json.loads(config_path.read_text())
        opponents = config["opponents"]
        if not isinstance(opponents, list) or not opponents:
            raise ValueError("opponents must be a non-empty list")
        cache = (config_path.parent / config.get("checkout_root", "updated")).resolve()
        cache = args.opponents_dir.expanduser().resolve() if args.opponents_dir else cache
        folders, entries = {}, []
        for opponent in opponents:
            repo, revision = opponent["repository"], opponent["revision"]
            name = repo.replace("/", "--")
            folder = cache / name if args.opponents_dir else fetch(repo, revision, cache)
            entry = folder / opponent.get("entrypoint", "bot.py")
            if not entry.is_file():
                raise ValueError(f"Missing opponent entry point: {entry}")
            folders[name] = folder
            entries.append(entry)
        simulator = folders[config["simulator"]]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"Invalid local lineup: {exc}")
    if args.fetch_only:
        for folder in folders.values():
            print(folder)
        return
    cmd = [sys.executable, str(ROOT / "tools/run_local_match.py"), "--sim", str(simulator),
           "--kit", str(ROOT), "--bot", str(ROOT / "main.py"), "--seed", str(args.seed)]
    python_path = config.get("opponent_python")
    opponent_python = (config_path.parent / python_path).resolve() if python_path else None
    if opponent_python and opponent_python.is_file():
        cmd.extend(["--opponent-python", str(opponent_python)])
    else:
        missing = [name for name in config.get("required_modules", []) if importlib.util.find_spec(name) is None]
        if missing:
            parser.error(f"Opponent environment missing modules: {', '.join(missing)}; see docs/local-simulator.md")
    for entry in entries:
        cmd.extend(["--opponent", str(entry)])
    if args.trace:
        cmd.extend(["--trace", str(args.trace.expanduser().resolve())])
    os.chdir(ROOT)
    os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
