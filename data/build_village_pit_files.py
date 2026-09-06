import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


base_dir = Path(__file__).resolve().parent

village_file = base_dir / "village_data.txt"
pit_file = base_dir / "pit_data.txt"

output_dir = base_dir / "pits_by_village"
index_file = base_dir / "village_index.json"


def normalize_name(name):
    return " ".join(name.strip().lower().split())


def display_name(name):
    return " ".join(
        word[:1].upper() + word[1:]
        for word in name.strip().split()
    )


def make_filename(name):
    normalized = normalize_name(name)

    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")

    if not slug:
        slug = "village"

    short_hash = hashlib.sha1(
        normalized.encode("utf-8")
    ).hexdigest()[:8]

    return f"{slug}-{short_hash}.json"


# make sure both source files exist

if not village_file.exists():
    raise FileNotFoundError("village_data.txt was not found")

if not pit_file.exists():
    raise FileNotFoundError("pit_data.txt was not found")


# create a dataset version from both source files

version_hash = hashlib.sha256()

version_hash.update(village_file.read_bytes())
version_hash.update(b"\0")
version_hash.update(pit_file.read_bytes())

dataset_version = version_hash.hexdigest()[:16]


# read village data

villages = {}

with village_file.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, delimiter="\t")

    next(reader, None)

    for row in reader:
        if len(row) < 4:
            continue

        raw_name = row[0].strip()

        if not raw_name:
            continue

        key = normalize_name(raw_name)

        try:
            pit_count = int(float(row[1]))
        except (ValueError, TypeError):
            pit_count = 0

        try:
            latitude = float(row[2])
            longitude = float(row[3])
        except (ValueError, TypeError):
            print(f"warning: invalid coordinates for village: {raw_name}")
            continue

        villages[key] = {
            "name": display_name(raw_name),
            "pitCount": pit_count,
            "lat": latitude,
            "lon": longitude
        }


# read and group pit data by village

pits_by_village = defaultdict(list)

with pit_file.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, delimiter="\t")

    next(reader, None)

    for row in reader:
        if len(row) < 7:
            continue

        try:
            latitude = float(row[1].strip())
            longitude = float(row[2].strip())
        except (ValueError, TypeError):
            continue

        raw_village = row[3].strip()

        if not raw_village or raw_village == "--":
            continue

        key = normalize_name(raw_village)

        date = row[5].strip()
        image = row[6].strip()

        pits_by_village[key].append({
            "lat": latitude,
            "lon": longitude,
            "date": date,
            "image": image
        })


# clear old generated village files

output_dir.mkdir(exist_ok=True)

for old_file in output_dir.glob("*.json"):
    old_file.unlink()


# create new village pit files and index

index_villages = []

for key, village in villages.items():

    pits = pits_by_village.get(key, [])

    actual_pit_count = len(pits)

    if actual_pit_count != village["pitCount"]:
        print(
            f"warning: {village['name']} says "
            f"{village['pitCount']} pits in village_data.txt "
            f"but {actual_pit_count} valid pits were found in pit_data.txt"
        )

    if pits:
        latitudes = [pit["lat"] for pit in pits]
        longitudes = [pit["lon"] for pit in pits]

        bounds = {
            "minLat": min(latitudes),
            "maxLat": max(latitudes),
            "minLon": min(longitudes),
            "maxLon": max(longitudes)
        }

        filename = make_filename(village["name"])

        output_path = output_dir / filename

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                pits,
                file,
                separators=(",", ":"),
                ensure_ascii=False
            )

    else:
        bounds = None
        filename = None

    index_villages.append({
        "name": village["name"],
        "pitCount": village["pitCount"],
        "actualPitCount": actual_pit_count,
        "lat": village["lat"],
        "lon": village["lon"],
        "bounds": bounds,
        "pitFile": filename
    })


# warn about villages that appear only in pit_data.txt

for key in pits_by_village:
    if key not in villages:
        print(
            "warning: village appears in pit_data.txt but not "
            f"village_data.txt: {display_name(key)}"
        )


# write lightweight index used by the map

index_data = {
    "version": dataset_version,
    "villages": index_villages
}

with index_file.open("w", encoding="utf-8") as file:
    json.dump(
        index_data,
        file,
        indent=2,
        ensure_ascii=False
    )


print()
print("build complete")
print(f"dataset version: {dataset_version}")
print(f"villages: {len(index_villages)}")
print(f"pit files created: {len(list(output_dir.glob('*.json')))}")
