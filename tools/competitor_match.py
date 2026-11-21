"""Run the team's fixed competitor lineup. Fetch pinned opponents on first use."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOS = {
    "shanmukha-here/eagle-eye-mech-royale": "6c7bb86707e76a288050da27e945f076f78227cc",
    "atharvatripathi2026/gtgoats_mech_royale": "ad3ffbb4e16e501790d5fbe5ca68dbd8497421d3",
    "devakchow/team-kanyaraasi-mech-royale": "52f5adf1b12ad360368545ab8b676ff681f1669f",
    "AbhirajTiwari12/mech-royale-bot": "2969326aed37fc94b98e19c1128e1b9d32fa284f",
}


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
    parser.add_argument("--seed", type=int, default=420000)
    parser.add_argument("--opponents-dir", type=Path,
                        help="Use the already unpacked mech-competitor-review folders.")
    parser.add_argument("--fetch-only", action="store_true", help="Download the pinned opponents without running a match.")
    args = parser.parse_args()
    folders = []
    for repo, revision in REPOS.items():
        folder = (args.opponents_dir.expanduser().resolve() / repo.replace("/", "--")
                  if args.opponents_dir else fetch(repo, revision, ROOT / "competitors"))
        if not (folder / "bot.py").is_file():
            parser.error(f"Missing opponent: {folder / 'bot.py'}")
        folders.append(folder)
    if args.fetch_only:
        for folder in folders:
            print(folder)
        return
    cmd = [sys.executable, str(ROOT / "tools/run_local_match.py"), "--sim", str(folders[0]),
           "--kit", str(ROOT), "--bot", str(ROOT / "main.py"), "--seed", str(args.seed)]
    for folder in folders:
        cmd.extend(["--opponent", str(folder / "bot.py")])
    os.chdir(ROOT)
    os.execv(sys.executable, cmd)


if __name__ == "__main__":
    main()
