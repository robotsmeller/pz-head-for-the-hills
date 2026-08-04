"""Assemble the Steam Workshop package for Head for the Hills!

PZ uploads from Zomboid/Workshop/<item>/, which has to look like this:

    Zomboid/Workshop/HeadForTheHills/
        workshop.txt
        preview.png
        Contents/mods/HeadForTheHills/
            mod.info, poster.png, 42/...

That is the same shape as the already-published Zomboid/Workshop/Unbreaker,
which is where the layout came from. The repo is the source of truth and this
script only ever writes into the Workshop folder.

    python scripts/build_workshop.py            build it
    python scripts/build_workshop.py --check    report what would change

The mod itself reaches the game through a directory junction at Zomboid/mods,
which is the development path. This is the publishing path and the two are
deliberately separate: a half-finished edit should not become a Workshop
update just because the game was launched.
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD_ID = "HeadForTheHills"
ITEM = Path.home() / "Zomboid" / "Workshop" / MOD_ID

SOURCES = {
    "workshop.txt": REPO / "workshop" / "workshop.txt",
    "preview.png": REPO / "assets" / "preview.png",
}
MOD_SOURCE = REPO / "mod"

# Never copied into the package. The originals are repo bookkeeping, and a
# .gitkeep in an otherwise empty folder would ship an empty folder.
EXCLUDE = {".gitkeep"}


def mod_files():
    """Every file under mod/, as (source, path relative to the mod root)."""
    for path in sorted(MOD_SOURCE.rglob("*")):
        if path.is_file() and path.name not in EXCLUDE:
            yield path, path.relative_to(MOD_SOURCE)


def planned():
    """The full file list the package should contain, as {destination: source}."""
    plan = {ITEM / name: source for name, source in SOURCES.items()}
    contents = ITEM / "Contents" / "mods" / MOD_ID
    for source, relative in mod_files():
        plan[contents / relative] = source
    return plan


def check(plan):
    missing, changed = [], []
    for destination, source in plan.items():
        if not destination.exists():
            missing.append(destination)
        elif not filecmp.cmp(source, destination, shallow=False):
            changed.append(destination)

    stale = []
    if ITEM.exists():
        wanted = set(plan)
        for path in ITEM.rglob("*"):
            if path.is_file() and path not in wanted:
                stale.append(path)
    return missing, changed, stale


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report what would change without writing")
    args = parser.parse_args()

    for name, source in SOURCES.items():
        if not source.exists():
            print(f"FAILED: {source} is missing")
            return 1
    if not (MOD_SOURCE / "mod.info").exists():
        print(f"FAILED: {MOD_SOURCE / 'mod.info'} is missing")
        return 1

    # B42 silently rejects a mod whose versioned mod.info is missing or out of
    # step with the root one: no entry in the mods list and nothing in
    # console.txt. Cheaper to fail here than to work out why in game.
    root, versioned = MOD_SOURCE / "mod.info", MOD_SOURCE / "42" / "mod.info"
    if not versioned.exists():
        print(f"FAILED: {versioned} is missing; B42 will not load the mod")
        return 1
    if not filecmp.cmp(root, versioned, shallow=False):
        print("FAILED: mod/mod.info and mod/42/mod.info differ; B42 needs both "
              "and they must match")
        return 1

    plan = planned()
    missing, changed, stale = check(plan)

    if args.check:
        for label, paths in (("missing", missing), ("changed", changed),
                             ("no longer in the repo", stale)):
            for path in paths:
                print(f"  {label:22} {path.relative_to(ITEM)}")
        if not (missing or changed or stale):
            print(f"  up to date: {len(plan)} files")
        return 0

    for destination, source in plan.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for path in stale:
        path.unlink()

    print(f"  built {ITEM}")
    print(f"  {len(plan)} files, {len(changed)} updated, {len(missing)} added, "
          f"{len(stale)} removed")
    print("\n  Upload from the game: main menu, Workshop, then this item.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
