#!/usr/bin/env python3
"""
Log a new beach or taco spot into data/places.json.

    python3 tools/add_place.py

Interactive by default: paste a Google Maps link (or a name), answer a few
prompts, and the entry is appended. Coordinates come straight out of the link
when it has them, otherwise from OpenStreetMap, gated on precision so a city
centroid is never written as though it were the restaurant.

Everything can also be passed as flags for a one-liner:

    python3 tools/add_place.py --url "https://maps.app.goo.gl/..." \\
        --type taco --rating 5 --notes "Adobada is the move."
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geocode import UA, ENDPOINT, precise          # noqa: E402
from import_takeout import city_country            # noqa: E402
from merge_candidates import COUNTRY_ALIASES       # noqa: E402

LIVE = "data/places.json"
VALID_TYPES = ("taco", "beach")


# --- Reading a Google Maps link ------------------------------------------------

COORD_PATTERNS = [
    r"@(-?\d+\.\d+),(-?\d+\.\d+)",              # /maps/@37.77,-122.41,15z
    r"[?&]q=(-?\d+\.\d+),\s*(-?\d+\.\d+)",      # ?q=37.77,-122.41
    r"[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)",        # ?ll=...
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",          # embedded place coords
    r"/search/(-?\d+\.\d+),\s*(-?\d+\.\d+)",    # /maps/search/37.77,-122.41
]


def expand(url):
    """Follow a maps.app.goo.gl short link to the full URL."""
    if "goo.gl" not in url and "maps.app" not in url:
        return url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.geturl()
    except Exception as exc:
        print(f"  (could not expand short link: {exc})")
        return url


def parse_maps_url(url):
    """Pull (name, lat, lng) out of a Google Maps URL where possible."""
    url = expand(url)
    lat = lng = None
    for pat in COORD_PATTERNS:
        m = re.search(pat, url)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            break
    name = ""
    m = re.search(r"/maps/place/([^/@?]+)", url)
    if m:
        name = urllib.parse.unquote_plus(m.group(1)).strip()
    if not name:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [""])[0]
        if q and not re.match(r"^-?\d+\.\d+", q):
            name = q.strip()
    return name, lat, lng, url


# --- Geocoding -----------------------------------------------------------------

def geocode(query):
    params = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 1})
    req = urllib.request.Request(ENDPOINT + params, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        results = json.load(r)
    time.sleep(1.1)                     # Nominatim asks for 1 request/second
    return [r for r in results if precise(r)]


REVERSE = "https://nominatim.openstreetmap.org/reverse?"


def reverse_geocode(lat, lng):
    """Fill in city/region/country when coordinates came from a Maps link."""
    params = urllib.parse.urlencode(
        {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 14, "addressdetails": 1})
    req = urllib.request.Request(REVERSE + params, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.load(r)
    except Exception as exc:
        print(f"  (reverse lookup failed: {exc})")
        return {}
    finally:
        time.sleep(1.1)
    if "address" not in res:
        return {}
    addr = res["address"]
    return {
        # A remote beach often has no town at all; the county still tells the
        # reader roughly where it is, which beats a blank line on the card.
        "city": (addr.get("city") or addr.get("town") or addr.get("village")
                 or addr.get("municipality") or addr.get("suburb")
                 or addr.get("county") or ""),
        "region": addr.get("state", ""),
        "country": addr.get("country", ""),
    }


def pick(results):
    if not results:
        return None
    if len(results) == 1:
        return results[0]
    print("\n  Several matches:")
    for i, r in enumerate(results, 1):
        print(f"    {i}. {r['display_name'][:96]}")
    while True:
        raw = input("  Which one? (number, or blank to skip) ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(results):
            return results[int(raw) - 1]


def place_from(res):
    addr = res.get("address", {})
    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("municipality") or addr.get("suburb") or "")
    return {
        "lat": round(float(res["lat"]), 6),
        "lng": round(float(res["lon"]), 6),
        "city": city,
        "region": addr.get("state", ""),
        "country": addr.get("country", ""),
    }


# --- Prompts -------------------------------------------------------------------

def ask(label, default="", required=False, choices=None):
    while True:
        suffix = f" [{default}]" if default else ""
        if choices:
            suffix = f" ({'/'.join(choices)})" + suffix
        val = input(f"  {label}{suffix}: ").strip() or default
        if choices and val not in choices:
            print(f"    must be one of {', '.join(choices)}")
            continue
        if required and not val:
            print("    required")
            continue
        return val


def ask_rating(default=""):
    while True:
        val = input(f"  Rating 1-5 (blank to skip){f' [{default}]' if default else ''}: ").strip() or default
        if not val:
            return None
        if val.isdigit() and 1 <= int(val) <= 5:
            return int(val)
        print("    1 to 5, or blank")


def ask_date(default):
    while True:
        val = input(f"  Visited [{default}]: ").strip() or default
        if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            return val
        print("    use YYYY-MM-DD")


# --- Writing -------------------------------------------------------------------

def load(path):
    if not os.path.exists(path):
        return {"places": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Google Maps link for the place")
    ap.add_argument("--name")
    ap.add_argument("--type", choices=VALID_TYPES)
    ap.add_argument("--city")
    ap.add_argument("--country")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lng", type=float)
    ap.add_argument("--rating", type=int, choices=range(1, 6))
    ap.add_argument("--visited", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--notes")
    ap.add_argument("--photo")
    ap.add_argument("--file", default=LIVE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    interactive = not (args.name or args.url)
    entry = {}
    url = args.url or ""

    if interactive:
        print("\nAdd a spot to the log. Paste a Google Maps link, or just type a name.\n")
        url = input("  Google Maps link (or blank): ").strip()

    guessed_name = ""
    if url:
        guessed_name, lat, lng, url = parse_maps_url(url)
        if lat is not None:
            entry.update(lat=round(lat, 6), lng=round(lng, 6))
            print(f"  found coordinates in the link: {lat:.5f},{lng:.5f}")
        if guessed_name:
            print(f"  found name in the link: {guessed_name}")
        entry["mapsUrl"] = url

    name = args.name or guessed_name
    if interactive or not name:
        name = ask("Name", default=name, required=True)
    entry["name"] = name

    kind = args.type or (ask("Type", default="taco", choices=list(VALID_TYPES))
                         if interactive else None)
    if kind not in VALID_TYPES:
        sys.exit(f"--type must be one of {', '.join(VALID_TYPES)}")
    entry["type"] = kind

    if args.lat is not None and args.lng is not None:
        entry.update(lat=args.lat, lng=args.lng)

    # Fill in location from OpenStreetMap when the link didn't carry it.
    if "lat" not in entry:
        hint = args.city or (ask("City or address (helps the lookup)") if interactive else "")
        query = ", ".join(x for x in (name, hint) if x)
        print(f"  looking up \"{query}\" ...")
        try:
            hits = geocode(query)
        except Exception as exc:
            hits = []
            print(f"  lookup failed: {exc}")
        res = pick(hits) if interactive else (hits[0] if hits else None)
        if res:
            print(f"  -> {res['display_name'][:90]}")
            entry.update(place_from(res))
        else:
            print("  No confident match. Coordinates are required —")
            print("  open the place in Google Maps, right-click the pin, and copy the numbers.")
            if not interactive:
                sys.exit(1)
            entry["lat"] = float(ask("Latitude", required=True))
            entry["lng"] = float(ask("Longitude", required=True))

    # --city doubles as a lookup hint ("San Diego, California"), so it must not
    # overwrite the cleaner city the geocoder parsed out.
    # Coordinates straight from a Maps link carry no place name with them.
    if entry.get("lat") is not None and not entry.get("city"):
        print("  filling in the location from the coordinates ...")
        for k, v in reverse_geocode(entry["lat"], entry["lng"]).items():
            if v:
                entry[k] = v

    for field, flag in (("city", args.city), ("country", args.country)):
        if flag and not entry.get(field):
            entry[field] = flag
    if interactive:
        entry["city"] = ask("City", default=entry.get("city", ""))
        entry["region"] = ask("Region/state", default=entry.get("region", ""))
        entry["country"] = ask("Country", default=entry.get("country", ""))

    if entry.get("country"):
        c = entry["country"].strip()
        entry["country"] = COUNTRY_ALIASES.get(c.lower(), c)

    today = date.today().isoformat()
    entry["visited"] = args.visited or (ask_date(today) if interactive else today)
    rating = args.rating if args.rating else (ask_rating() if interactive else None)
    if rating:
        entry["rating"] = rating
    notes = args.notes or (ask("Notes") if interactive else "")
    if notes:
        entry["notes"] = " ".join(notes.split())
    photo = args.photo or (ask("Photo path under images/places/") if interactive else "")
    if photo:
        entry["photo"] = photo

    # Order the keys the way the rest of the file reads.
    order = ["name", "type", "lat", "lng", "city", "region", "country",
             "visited", "rating", "notes", "mapsUrl", "photo", "post"]
    entry = {k: entry[k] for k in order if entry.get(k) not in ("", None)}

    doc = load(args.file)
    dupe = next((e for e in doc["places"]
                 if round(e["lat"], 4) == round(entry["lat"], 4)
                 and round(e["lng"], 4) == round(entry["lng"], 4)), None)
    if dupe:
        print(f"\n  Already logged at these coordinates: {dupe['name']}")
        if not interactive or input("  Add anyway? (y/N) ").strip().lower() != "y":
            sys.exit(0)

    print("\n" + json.dumps(entry, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("\n(dry run — nothing written)")
        return

    doc["places"].append(entry)
    doc["places"].sort(key=lambda e: (e.get("visited", ""), e["name"]), reverse=True)
    save(args.file, doc)
    print(f"\nAdded to {args.file} — {len(doc['places'])} spots total.")
    print("\nPush it live with:")
    print(f'  git add {args.file} && git commit -m "Add {entry["name"]}" && git push')


if __name__ == "__main__":
    main()
