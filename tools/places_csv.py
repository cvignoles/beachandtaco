#!/usr/bin/env python3
"""
Move the place log between data/places.json and a spreadsheet-friendly CSV.

    python3 tools/places_csv.py export                  # json -> data/places.csv
    python3 tools/places_csv.py import                  # csv  -> json  (checks only)
    python3 tools/places_csv.py import --apply          # csv  -> json  (writes)
    python3 tools/places_csv.py import --apply --geocode # also look up blank coordinates

Edit the CSV in Excel, Numbers or Sheets, then import it back. The export is
written with a UTF-8 BOM so Excel does not mangle the accents in names like
Praia da Falesia or Los Canos de Meca.

Import refuses to write anything if a row is invalid, so a typo cannot quietly
empty the map. Blank rows are skipped, so you can leave spacing in the sheet.
"""
import argparse, csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LIVE = "data/places.json"
CSV_PATH = "data/places.csv"
COLUMNS = ["name", "type", "lat", "lng", "city", "region", "country",
           "visited", "rating", "notes", "mapsUrl", "photo", "post"]
REQUIRED = ["name", "type"]
VALID_TYPES = ("taco", "beach")


# --- Export --------------------------------------------------------------------

def do_export(args):
    doc = json.load(open(args.json, encoding="utf-8"))
    places = doc.get("places", [])
    places = sorted(places, key=lambda e: (e.get("visited", ""), e.get("name", "")),
                    reverse=True)
    # utf-8-sig writes the BOM Excel needs to read accents correctly.
    with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for p in places:
            w.writerow({c: p.get(c, "") for c in COLUMNS})
    print(f"{len(places)} places -> {args.csv}")
    kinds = {}
    for p in places:
        kinds[p.get("type", "?")] = kinds.get(p.get("type", "?"), 0) + 1
    print("  " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())))
    blank = [c for c in COLUMNS if not any(p.get(c) for p in places)]
    if blank:
        print(f"  columns nobody uses yet: {', '.join(blank)}")


# --- Import --------------------------------------------------------------------

def num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def validate(row, i, geocoding):
    """Return (entry, [problems]) for one CSV row."""
    problems = []
    e = {}

    for col in REQUIRED:
        if not (row.get(col) or "").strip():
            problems.append(f"row {i}: {col} is empty")

    name = (row.get("name") or "").strip()
    kind = (row.get("type") or "").strip().lower()
    if kind and kind not in VALID_TYPES:
        problems.append(f"row {i} ({name}): type is \"{kind}\", must be taco or beach")
    e["name"], e["type"] = name, kind

    lat, lng = num(row.get("lat")), num(row.get("lng"))
    if lat is None or lng is None:
        if not geocoding:
            problems.append(f"row {i} ({name}): missing coordinates "
                            f"— fill lat/lng, or re-run with --geocode")
    else:
        if not (-90 <= lat <= 90):
            problems.append(f"row {i} ({name}): latitude {lat} is out of range")
        if not (-180 <= lng <= 180):
            problems.append(f"row {i} ({name}): longitude {lng} is out of range")
        if lat == 0 and lng == 0:
            problems.append(f"row {i} ({name}): 0,0 is the Atlantic, not a real location")
        e["lat"], e["lng"] = round(lat, 6), round(lng, 6)

    for col in ("city", "region", "country", "mapsUrl", "photo", "post"):
        v = (row.get(col) or "").strip()
        if v:
            e[col] = v

    notes = (row.get("notes") or "").strip()
    if notes:
        e["notes"] = " ".join(notes.split())

    visited = (row.get("visited") or "").strip()
    if visited:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", visited):
            problems.append(f"row {i} ({name}): visited \"{visited}\" must be YYYY-MM-DD")
        else:
            e["visited"] = visited

    rating = (row.get("rating") or "").strip()
    if rating:
        r = num(rating)
        if r is None or not (1 <= r <= 5):
            problems.append(f"row {i} ({name}): rating \"{rating}\" must be 1-5")
        else:
            e["rating"] = int(r)

    return e, problems


def do_import(args):
    if not os.path.exists(args.csv):
        sys.exit(f"{args.csv} not found — run `export` first.")

    with open(args.csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    missing_cols = [c for c in REQUIRED if c not in (rows[0].keys() if rows else [])]
    if missing_cols:
        sys.exit(f"CSV is missing required column(s): {', '.join(missing_cols)}")

    entries, problems = [], []
    for i, row in enumerate(rows, start=2):          # row 1 is the header
        if not any((v or "").strip() for v in row.values()):
            continue                                  # blank spacer row
        e, probs = validate(row, i, args.geocode)
        problems += probs
        if not probs or (args.geocode and all("missing coordinates" in p for p in probs)):
            entries.append(e)

    need_geo = [e for e in entries if "lat" not in e]
    if args.geocode and need_geo:
        from geocode import UA, ENDPOINT, precise
        import urllib.parse, urllib.request, time
        print(f"looking up {len(need_geo)} row(s) without coordinates …")
        for e in need_geo:
            q = ", ".join(x for x in (e["name"], e.get("city"), e.get("country")) if x)
            try:
                url = ENDPOINT + urllib.parse.urlencode(
                    {"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1})
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    hits = [h for h in json.load(r) if precise(h)]
                time.sleep(1.1)
            except Exception as exc:
                hits = []
                print(f"  !! {e['name']}: {exc}")
            if hits:
                h = hits[0]
                e["lat"], e["lng"] = round(float(h["lat"]), 6), round(float(h["lon"]), 6)
                print(f"  ok {e['name']} -> {e['lat']},{e['lng']}")
                print(f"       {h['display_name'][:88]}")
            else:
                problems.append(f"{e['name']}: no confident match — add lat/lng by hand")

    # Anything still without coordinates cannot go on the map.
    entries = [e for e in entries if "lat" in e and "lng" in e]

    seen, dupes = {}, []
    for e in entries:
        key = (round(e["lat"], 4), round(e["lng"], 4))
        if key in seen:
            dupes.append(f"{e['name']} and {seen[key]} share the same coordinates")
        seen[key] = e["name"]

    print(f"\n{len(rows)} rows read, {len(entries)} valid places")
    for d in dupes:
        print(f"  note: {d}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        if not args.force:
            sys.exit("\nNothing written. Fix the rows above, or pass --force to write "
                     "only the valid ones.")

    entries = [{k: e[k] for k in COLUMNS if k in e} for e in entries]
    entries.sort(key=lambda e: (e.get("visited", ""), e["name"]), reverse=True)

    out = {}
    if os.path.exists(args.json):
        old = json.load(open(args.json, encoding="utf-8"))
        if "_schema" in old:
            out["_schema"] = old["_schema"]
        was = len(old.get("places", []))
        delta = len(entries) - was
        print(f"\n{was} places currently live -> {len(entries)} "
              f"({delta:+d})")
    out["places"] = entries

    if not args.apply:
        print("\n(check only — pass --apply to write)")
        return
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"written to {args.json}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export", help="write data/places.csv from the JSON")
    ex.add_argument("--json", default=LIVE)
    ex.add_argument("--csv", default=CSV_PATH)
    ex.set_defaults(func=do_export)

    im = sub.add_parser("import", help="rebuild the JSON from the CSV")
    im.add_argument("--json", default=LIVE)
    im.add_argument("--csv", default=CSV_PATH)
    im.add_argument("--apply", action="store_true", help="actually write the JSON")
    im.add_argument("--geocode", action="store_true",
                    help="look up rows left without coordinates")
    im.add_argument("--force", action="store_true",
                    help="write the valid rows even if others have problems")
    im.set_defaults(func=do_import)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
