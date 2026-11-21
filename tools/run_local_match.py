"""Run the current bot against a repeatable local field."""
import argparse
from contextlib import ExitStack
import gzip
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", type=Path, required=True)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--bot", type=Path, default=Path("example_bot.py"))
    parser.add_argument("--bot-env", action="append", default=[], metavar="NAME=VALUE",
                        help="Set an environment variable for the subject bot only; repeat for multiple factors.")
    parser.add_argument("--seed", type=int, default=420000)
    parser.add_argument("--trace", type=Path, help="Write subject observations and actions to JSONL.")
    parser.add_argument("--opponent", action="append", type=Path, default=[],
                        help="Python bot entry point. Repeat to fill more FFA slots.")
    parser.add_argument("--opponent-python", type=Path, help="Python interpreter used for opponent entry points.")
    parser.add_argument("--opponent-image", action="append", default=[],
                        help="Locally built mechfight Docker image, for any language.")
    args = parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', value) for value in args.bot_env):
        parser.error('--bot-env must be NAME=VALUE')
    if len(args.opponent) + len(args.opponent_image) > 15:
        parser.error("The arena has 15 opponent slots.")
    sim, kit, bot = (p.resolve(strict=True) for p in (args.sim, args.kit, args.bot))
    sys.path.insert(0, str(sim))
    from local_sim.game import Match
    from local_sim.geometry import Map
    from local_sim.pool import scripted
    from local_sim import wire
    from local_sim.wire import Client

    if sys.platform == "darwin":
        # macOS does not support setting RLIMIT_AS as Linux does. Keep core
        # dumps disabled; match memory enforcement still requires Docker/Linux.
        import resource
        def mac_child_limits():
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        wire.child_limits = mac_child_limits

    with gzip.open(kit / "check/stream.jsonl.gz", "rt") as stream:
        hello = json.loads(next(stream))
    hello["map"]["dir"] = str(kit / "arena")
    with tempfile.TemporaryDirectory() as tmp:
        lib = Path(tmp) / "geometry.so"
        subprocess.run(["cc", "-O3", "-shared", "-fPIC", str(sim / "local_sim/geometry.c"),
                        "-lm", "-o", str(lib)], check=True)
        arena = Map(kit / "arena", hello["config"], lib)
        roles = ["hunter", "looter", "edge", "camper"] * 3 + ["hunter", "looter", "edge"]
        entrants = [(str(bot), ['env', *args.bot_env, sys.executable, "-u", str(bot)], False)]
        for entry in args.opponent:
            path = entry.resolve(strict=True)
            interpreter = str(args.opponent_python.resolve(strict=True)) if args.opponent_python else sys.executable
            entrants.append((str(path), [interpreter, "-u", str(path)], False))
        for image in args.opponent_image:
            command = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
                       "--memory", "512m", "--cpus", "1", "--user", "65534:65534",
                       "--tmpfs", "/tmp:rw,size=64m", "-v", f"{kit / 'arena'}:/arena:ro", image]
            entrants.append((image, command, True))
        match = Match(arena, hello, args.seed, roles, len(entrants) > 1)
        player = match.players[match.subject]
        clients = {}
        names = {}
        with ExitStack() as cleanup:
            trace = cleanup.enter_context(args.trace.open("w", encoding="utf-8")) if args.trace else None
            for slot, (name, command, docker) in zip([player.id, *match.order], entrants):
                greeting = dict(hello, slot=slot, seed=((slot + 1) * 1779033703) % 2**32)
                if docker:
                    greeting["map"] = dict(hello["map"], dir="/arena")
                client = Client(command, greeting)
                cleanup.callback(client.close)
                if client.dead:
                    raise SystemExit(f"Startup handshake failed for {name}")
                clients[slot] = client
                names[slot] = name
            place = None
            while place is None:
                match.refresh_team()
                for mech in match.players:
                    if mech.life:
                        if mech.id in clients:
                            client = clients[mech.id]
                            observation = match.obs(mech)
                            late_before, bad_before = client.late, client.bad
                            started = time.perf_counter()
                            mech.action = client.act(observation)
                            if trace and mech.id == player.id:
                                trace.write(json.dumps({"type":"step", "obs":observation, "action":mech.action,
                                                        "elapsed_ms":(time.perf_counter()-started)*1000,
                                                        "late":client.late-late_before,
                                                        "invalid":client.bad-bad_before}, separators=(",", ":")) + "\n")
                            if client.dead:
                                raise SystemExit(f"Bot stopped during match: {names[mech.id]}")
                        else:
                            mech.action = scripted(match, mech)
                        mech.events = []
                place = match.advance()
                if place is None:
                    place = match.advance()
            subject_client = clients[player.id]
            if trace:
                trace.write(json.dumps({"type":"end", "t":match.t, "place":place,
                                        "events":player.events, "self":player.s}, separators=(",", ":")) + "\n")
            subject_client.end(place, player.kills)
            results = [dict(bot=names[i], slot=i, kills=m.kills, alive=m.life,
                            late=clients[i].late, invalid=clients[i].bad)
                       for i in clients if i != player.id for m in [match.players[i]]]
            print(json.dumps(dict(seed=args.seed, place=place, points=16-place, kills=player.kills,
                                  game_seconds=round(match.t, 2), late=subject_client.late,
                                  invalid=subject_client.bad, opponents=results)))


if __name__ == "__main__":
    main()
