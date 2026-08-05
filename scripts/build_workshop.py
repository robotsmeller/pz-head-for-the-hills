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
import struct
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

# The Workshop page description, one file, BBCode and all.
#
# WHY THIS IS WIRED IN: workshop.txt carried a single `description=See workshop
# page`, which reads like a placeholder the uploader ignores. It is not. PZ
# pushes whatever `description=` lines it finds, so every upload replaced the
# real page text with that one line. It happened twice before anyone worked out
# what was doing it, because the upload reports success and the damage is only
# visible on the website afterwards.
#
# The format is one `description=` per line of text, blank lines included as a
# bare `description=`. Zomboid/Workshop/ModTemplate/workshop.txt is the vanilla
# example. Lines may contain `=` themselves, as BBCode urls do, which is fine:
# the parser splits on the first one only.
DESCRIPTION = REPO / "assets" / "workshop-description.txt"

# PZ's in-game uploader refuses anything else, with "The preview.png file must be
# exactly 256x256 pixels in size." Steam's own 1 MB cap is the constraint people
# write about, and it is not the binding one here. Unbreaker ships a 1024px
# preview because it uploads through SteamCMD, which does not check.
PREVIEW_SIZE = (256, 256)
MOD_SOURCE = REPO / "mod"

# Never copied into the package. The originals are repo bookkeeping, and a
# .gitkeep in an otherwise empty folder would ship an empty folder.
EXCLUDE = {".gitkeep"}


def description_lines():
    """The page text as `description=` lines, one per source line."""
    text = DESCRIPTION.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [f"description={line}" for line in text.rstrip("\n").split("\n")]


def workshop_txt(existing):
    """workshop.txt with our description, keeping the uploader's own fields.

    `id` and `visibility` are written BY PZ, so the staged file is authoritative
    for those and the repo copy must not clobber them. The description is the
    opposite: the repo is authoritative and the staged copy is whatever survived
    the last upload. So this merges rather than copying either way round.
    """
    source = existing if existing else SOURCES["workshop.txt"]
    kept, wrote_description = [], False
    for line in source.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n"):
        if line.startswith("description="):
            # Collapse the old block down to one insertion point.
            if not wrote_description:
                kept.extend(description_lines())
                wrote_description = True
            continue
        kept.append(line)
    if not wrote_description:
        kept.extend(description_lines())
    return "\n".join(kept).rstrip("\n") + "\n"


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
        elif destination.name == "workshop.txt":
            # id and visibility belong to the uploader, the description belongs
            # to us, so compare against the merge rather than against either file.
            wanted = workshop_txt(destination)
            if destination.read_text(encoding="utf-8").replace("\r\n", "\n") != wanted:
                changed.append(destination)
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
    # Loud, because a missing description file would otherwise build a package
    # that quietly wipes the Workshop page on upload, which is the exact bug
    # this whole mechanism exists to stop.
    if not DESCRIPTION.exists():
        print(f"FAILED: {DESCRIPTION} is missing; uploading without it would "
              f"blank the Workshop page description")
        return 1
    if not (MOD_SOURCE / "mod.info").exists():
        print(f"FAILED: {MOD_SOURCE / 'mod.info'} is missing")
        return 1

    # Checked here rather than discovered halfway through the upload wizard.
    with open(SOURCES["preview.png"], "rb") as handle:
        header = handle.read(26)
    size = struct.unpack(">II", header[16:24]) if header[12:16] == b"IHDR" else None
    if size != PREVIEW_SIZE:
        print(f"FAILED: preview.png is {size[0]}x{size[1]} and the uploader "
              f"needs exactly {PREVIEW_SIZE[0]}x{PREVIEW_SIZE[1]}"
              if size else "FAILED: preview.png is not a readable PNG")
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
        # workshop.txt is written BY the uploader as well as read by it: PZ
        # stamps the assigned id into it on first publish and rewrites the
        # visibility to whatever was chosen. Copying the repo's copy over the
        # top would blank the id, and an upload with a blank id creates a
        # SECOND Workshop item rather than updating the first. So those fields
        # are left exactly as the uploader left them, and only the description
        # block is rewritten from the repo. Unbreaker carries the same warning
        # about the id, and the same description landmine.
        if destination.name == "workshop.txt":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                workshop_txt(destination if destination.exists() else None),
                encoding="utf-8")
            continue
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
