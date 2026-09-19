#!/usr/bin/env python3
"""
Merge curated candidates into data/places.json.

Drops the importer's internal `_` fields, skips anything still missing
coordinates, and matches existing entries on rounded coordinates so re-running
updates in place rather than duplicating.

    python3 tools/merge_candidates.py data/places.candidates.json --apply
"""
import argparse, json, os

LIVE = "data/places.json"
KEEP = ["name", "type", "lat", "lng", "city", "region", "country",
        "visited", "rating", "notes", "mapsUrl", "photo", "post"]

# Sources disagree on country names: Google says "Mexico", Nominatim says
# "México". Left alone they become two entries in the country filter.
COUNTRY_ALIASES = {
    "méxico": "Mexico", "mexico": "Mexico",
    "españa": "Spain", "spain": "Spain",
    "usa": "United States", "us": "United States",
    "united states of america": "United States",
    "united states": "United States",
    "portugal": "Portugal", "italia": "Italy", "france": "France",
    "deutschland": "Germany", "japan": "Japan", "日本": "Japan",
}


def clean(e):
    out = {k: e[k] for k in KEEP if k in e and e[k] not in ("", None)}
    if out.get("notes"):
        out["notes"] = " ".join(out["notes"].split())
    if out.get("country"):
        out["country"] = COUNTRY_ALIASES.get(out["country"].strip().lower(),
                                             out["country"].strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--live", default=LIVE)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--replace", action="store_true",
                    help="drop existing entries instead of merging into them")
    args = ap.parse_args()

    cand = json.load(open(args.candidates, encoding="utf-8"))["places"]
    ready = [c for c in cand if not c.get("_needs_geocode")]
    skipped = len(cand) - len(ready)

    doc = {"places": []}
    if os.path.exists(args.live):
        doc = json.load(open(args.live, encoding="utf-8"))
    schema = doc.get("_schema")
    existing = [] if args.replace else doc.get("places", [])

    index = {(round(e["lat"], 4), round(e["lng"], 4)): i
             for i, e in enumerate(existing)}
    merged = list(existing)
    added = updated = 0
    for c in ready:
        row = clean(c)
        key = (round(row["lat"], 4), round(row["lng"], 4))
        if key in index:
            merged[index[key]] = {**merged[index[key]], **row}
            updated += 1
        else:
            index[key] = len(merged)
            merged.append(row)
            added += 1

    merged.sort(key=lambda e: (e.get("visited", ""), e["name"]), reverse=True)
    out = {}
    if schema:
        out["_schema"] = schema
    out["places"] = merged

    print(f"added {added}, updated {updated}, skipped {skipped} without coordinates")
    print(f"total now {len(merged)}")
    if args.apply:
        with open(args.live, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"written to {args.live}")
    else:
        print("(dry run — pass --apply to write)")


if __name__ == "__main__":
    main()
