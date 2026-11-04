# Praxis KG Invasion — developer notes

This document explains how the Jak 3 mod Praxis KG Invasion works: its switch and zones, the Jak 2
models, the hooks in Jak 3's code, and how it was tested. The player guide is the root `README.md`.
The feature comes from the mod Haven City: New Dawn, where it was the war's second mode; it was
taken out of that mod and made standalone.

## 1. What it does

With the switch on (Mods menu, L3 + SELECT, **Praxis KG Invasion**), in Jak 3's city, at any point
of the story:

- the faction praxis-kguard (Jak 2's red and yellow Krimzon Guards, and red jetpack guards) fights
  the Freedom League's blue guards in the conflict zones;
- in a zone the two sides are all there is: no KG robot, spydroid, Metal Head or Wastelander comes
  out; outside the zones the city is Jak 3's;
- no guard vehicle flies, of either side;
- the citizens flee, and the Krimzon Guards attack them and Jak;
- the fight music is Jak 2's music of the fight against Baron Praxis (Jak 2's `DANGER4.MUS`,
  `drill-baron.gc`'s `'danger4`) instead of Jak 3's `fight1`: kept in the mod as
  `custom_assets/jak3/music/PKIDANG4.MUS`, copied by `game.gp` next to Jak 3's files, played as
  `'pkidang4` (the two games share the music format; Haven City: New Dawn plays Jak 2's this way).

A Jak 3 mission in the city (a `task-manager` process) sets its own factions and units: the
invasion steps aside until it ends. The switch is off at every boot; nothing changes while it is off.

## 2. Files

| File | Role |
|---|---|
| `goal_src/jak3/pc/features/praxis-kg-invasion.gc` (GAME) | Switch, zones, models' skeleton groups, looks and sides, every hook Jak 3's code calls, Mods menu entry |
| `goal_src/jak3/levels/city/war/pki-city.gc` (CWI) | The director: mission check, looks count, hatreds, citizens' panic; started by a wrapper of `traffic-manager-method-16` |
| `scripts/praxis_kg_invasion/make_models.py` | Builds the five models from the player's Jak 2 and Jak 3 rips |
| `custom_assets/jak3/music/PKIDANG4.MUS` | Jak 2's `DANGER4.MUS`, the fight music |
| `custom_assets/jak3/models/custom_levels/pki-*.glb` | The models `build-actor` reads |
| `custom_assets/jak3/models/ctypesa/`, `ctypesc/` | The same meshes, baked into those levels' `.fr3` by `task extract` |
| `goal_src/jak3/dgos/game.gd`, `cwi.gd`, `ctypesa.gd`, `ctypesc.gd`, `goal_src/jak3/game.gp` | Links the two `.gc` files and the five art groups |

## 3. Models

`make_models.py` reads `decompiler_out/jak2/levels/forresca/crimson-guard-lod0.glb`,
`crimson-guard-hover-lod0.glb` (same folder) and `decompiler_out/jak3/levels/ctypesa/crimson-guard-lod0.glb`.

| Model | Content | Level |
|---|---|---|
| `pki-kg-red` | Jak 2 guard mesh, normal armor, rifle, on Jak 3's guard skeleton and clips | CTYPESA |
| `pki-kg-red-gl` | The same with the grenade launcher | CTYPESA |
| `pki-kg-yellow` | Dark guard armor (yellow), rifle | CTYPESA |
| `pki-kg-yellow-gl` | Dark guard armor, grenade launcher | CTYPESA |
| `pki-hover-red` | Jak 2 jetpack guard, its 17 clips, idle, fly-forward and shoot0 first | CTYPESC |

The primitive lists come from Haven City: New Dawn's level port. A guard's model is chosen when its
process is made (`pki-guard-skel-name`); a Krimzon Guard then plays the blue guard's clips from
`crimson-guard-ag` (`pki-guard-clips`), which keeps Jak 3's animation pace. The jetpack guard is a
`flying-turret` drawn with `pki-hover-red` for one turret process in two (odd pid).

## 4. Zones

`*mod-praxis-kg-invasion-zones*` holds one bit per district, all nine on by default:

| Bit | Menu entry | Territories (`nav-territory-type`) |
|---|---|---|
| 0 | Port | `port-ff-deep`, `port-ff-near-kg`, `port-ff-kg-border` |
| 1 | Port, Metal Head border | `port-ff-near-mh`, `port-ff-mh-border` |
| 2 | Industrial Section A | `inda-kg-ff-border`, `inda-kg`, `inda-kg-deep` |
| 3 | Industrial Section B | `indb-kg-deep`, `indb-kg`, `indb-kg-ff-border` |
| 4 | Slums A | `sluma-ff-kg-border`, `sluma-ff`, `sluma-ff-deep` |
| 5 | Slums B | `slumb-ff-deep` |
| 6 | Slums C | `slumc-ff-deep` |
| 7 | Genc | `genc-border`, `genc` |
| 8 | Metal Head city | `mhcity-mh-ff-border`, `mhcity-mh`, `mhcity-mh-deep` |

These are the 21 regular territories of Jak 3's city; the `special*` ones are missions'. Changing the
switch or a zone rebuilds the city's traffic (`ctywide-activate`, as a death does), except during a
mission.

## 5. Hooks in Jak 3's code

Each marked line (`og:praxis-kg-invasion`) calls a function of `praxis-kg-invasion.gc` that answers
like the stock code while the invasion is off.

| File | Hook | Purpose |
|---|---|---|
| `levels/city/traffic/citizen/guard.gc` | `pki-guard-skel-name`, `pki-guard-clips`, `pki-guard-type`, `pki-attacker-type`, `pki-guard-flags`, `pki-guard-activated` | Look, clips, weapon (no tazer), attack-controller type 13, yellow = dark guard, enemy mask |
| `levels/city/protect/flying-turret.gc` | `pki-turret-skel-name`, `pki-unit-scale`, `pki-attacker-type`, `pki-hover-animate`, `pki-hover-nozzle!` | The jetpack guard on the turret code |
| `levels/city/common/kg-squad-member.gc` | `pki-hover-hatred` | The jetpack guard's targets: blue guards and Jak |
| `levels/city/common/guard-rifle.gc`, `guard-grenade.gc`, `guard-states.gc` | `pki-melee-ok?`, `pki-reload-speed`, `pki-reload-break-ok?` | Rifle butt for Jak only, faster reload, no same-frame state loop |
| `levels/city/traffic/citizen/citizen.gc` | `pki-shuffle-rate` | Shuffle steps at the pace of the ground covered |
| `engine/ai/enemy.gc` | `pki-death-start` | Death cloud of a custom model (the generic renderer can't draw it) |
| `levels/city/traffic/traffic-manager.gc`, `traffic-engine.gc` | `pki-want-count`, `pki-spawn-ok?`, `pki-get-from-inactive` (`pki-wake-ok?`) | Pools, types allowed in a zone, which sleeping unit goes out where |
| `levels/wascity/cty-faction.gc` | `pki-permission`, `pki-fight-music` | Spawn permissions in a zone, fight music |
| `levels/wascity/traffic-util.gc` | `pki-cell-dist` | Guards woken from further away and kept off screen longer |

The faction praxis-kguard is attack-controller target type 13, free in Jak 3's table of 17 types;
`pki-hatred-set!` (`pki-city.gc`) adds its three hatred entries.

## 6. Tests

Run on 2026-11-04 with a debug boot, the save of slot 1, Jak invulnerable, every zone on: 80 s in
the port, then 50 s in the industrial section, a count every 10 s.

| Where | Blue guards | Red | Yellow | Red jetpacks | KG robots, Metal Heads | KG aiming at blue | Blue aiming at KG | Music |
|---|---|---|---|---|---|---|---|---|
| Port | 3 to 6 | 2 to 4 | 1 to 3 | 1 to 2 | 0 | 2 to 6 | 3 to 6 | `portattk` (the first choice) |
| Industrial section | 4 to 9 | 4 to 7 | 1 to 3 | 2 to 3 | 0 | 4 to 9 | 4 to 9 | `portattk` |

The screenshots in `docs/img/mod/` come from that run. The game never crashed. A second run with
Jak 2's music, the same way (2026-11-05): port 1 to 6 blue, 1 to 3 red, 1 to 3 yellow, 0 to 3
jetpacks; industrial section 4 to 6 blue, 3 to 5 red, 2 yellow, 2 jetpacks; music `pkidang4` at
every count, the game's log showing `Load music pkidang4` and no error; no crash.

## 7. Limits

- The Krimzon Guards have no minimap icon of their own: their blue icon is removed
  (`pki-kg-icons-off`), the minimap has no red guard class.
- They speak Jak 3's guard lines.
- The fight music and the models are Jak 2's files kept in the repository: publish it as a private
  repository.
- Tested with a save whose story isn't over; a finished story's city has more guards and was not
  tested.
