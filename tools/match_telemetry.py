"""Compact observer for the local squad proxy. Never calls Match.obs or bot code."""
import hashlib
import json
import math
from collections import Counter


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def layout_hash(match):
    return fingerprint({
        'subject': match.subject, 'order': match.order, 'zone': match.zone_phases,
        'players': [(p.role, p.s) for p in match.players], 'crates': match.crates,
        'pickups': match.pickups, 'npcs': match.npcs, 'npc_cd': match.npc_cd,
        'drops': match.drop_plan,
    })


class Observer:
    def __init__(self, stream, match):
        self.stream = stream
        self.initial = layout_hash(match)
        self.roles = {p.id: p.role for p in match.players}
        self.subject = match.subject
        self.counts = Counter()
        self.damage = Counter()
        self.path_m = 0.
        self.last_pos = None
        self.phase = None

    def emit(self, tick, t, origin, kind, **values):
        row = dict(v=1, tick=tick, t=round(t, 3), origin=origin, kind=kind, **values)
        self.stream.write(json.dumps(row, separators=(',', ':')) + '\n')

    def position(self, pos):
        if self.last_pos is not None:
            self.path_m += math.dist(self.last_pos, pos[:2])
        self.last_pos = tuple(pos[:2])

    def events(self, tick, t, events, origin):
        for event in events:
            kind = event['type']
            self.counts[kind] += 1
            if kind == 'damaged':
                self.damage[event['weapon']] += event['amount']
            self.emit(tick, t, origin, 'event', event=event)

    def step(self, obs, action, phase):
        tick, t, me = obs['tick'], obs['t'], obs['self']
        self.position(me['pos'])
        self.events(tick, t, obs['events'], 'wire')
        if tick % 20 == 0 or phase != self.phase:
            self.emit(tick, t, 'wire', 'sample', pos=me['pos'], hp=me['hp'], max_hp=me['max_hp'],
                      energy=me['energy'], cubes=me['cubes'], upgrades=me['upgrades'],
                      weapons=[{k: v for k, v in w.items() if k != 'stats'} if w else None
                               for w in me['weapons']], in_zone=me['in_zone'],
                      mech_ids=[a['id'] for a in obs['mechs'] if a['kind'] == 'mech'],
                      cube_options=len(obs['cubes']), move=action.get('move'), fire=action.get('fire'))
        if self.phase != phase:
            self.emit(tick, t, 'simulator', 'phase', phase=phase)
            self.phase = phase

    def finish(self, match, player):
        self.position(player.s['pos'])
        self.events(match.tick, match.t, player.events, 'simulator')
        terminal = dict(alive=player.life, phase=match.phase, fatal_weapon=player.fatal_weapon,
                        fatal_source=player.fatal_source, hp=player.s['hp'], cubes=player.s['cubes'],
                        upgrades=player.s['upgrades'], weapons=[w['kind'] if w else None for w in player.s['weapons']])
        self.emit(match.tick, match.t, 'simulator', 'end', **terminal)
        return dict(schema_version=1, initial_layout_sha256=self.initial, terminal=terminal,
                    subject=self.subject, slot_roles=self.roles,
                    events=dict(self.counts), incoming_damage=dict(self.damage), xy_path_m=self.path_m)
