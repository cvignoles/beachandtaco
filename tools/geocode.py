#!/usr/bin/env python3
"""
Fill in coordinates for entries flagged `_needs_geocode`.

Uses OpenStreetMap Nominatim, which needs no API key and no billing account.
Nothing is written blind: each result is printed with the address Nominatim
matched, so a wrong hit is visible before it reaches the site.

    python3 tools/geocode.py data/places.candidates.json

Nominatim's usage policy requires a descriptive User-Agent and at most one
request per second; both are honored below.
"""
import argparse, json, sys, time, urllib.parse, urllib.request

UA = "BeachAndTaco.com place importer (one-off personal data migration)"
ENDPOINT = "https://nominatim.openstreetmap.org/search?"

# Extra context for names that are too generic to resolve on their own.
HINTS = {
    "tacko": "Chestnut Street, San Francisco, California",
    "oscars mexican seafood": "San Diego, California",
    "mission baja tacos": "San Diego, California",
    "nixtaco": "Roseville, California",
    "el tarasco": "Manhattan Beach, California",
    "galapos beach, são simão, portugal": "Praia de Galapos, Setubal, Portugal",
    "praia da falésia": "Albufeira, Algarve, Portugal",
    "los caños de meca": "Barbate, Cadiz, Spain",
    "bar miramar sayulita": "Sayulita, Nayarit, Mexico",
    # Google's Geocoding API could not place these three; OSM can, given the
    # street or the natural-feature name rather than the business name alone.
    "los caños de meca": "Playa de los Caños de Meca, Barbate, Cadiz, Spain",
    # Two Pacific Beach locations exist (703 Turquoise St and 746 Emerald St).
    # The Takeout CSV carries only a Google feature id, which OSM cannot resolve,
    # so this picks the original on Turquoise. Verify against your own memory.
    "oscars mexican seafood": "703 Turquoise St, San Diego, CA",
    "el tarasco": "El Tarasco, Rosecrans Avenue, Manhattan Beach, California",
}


# Nominatim happily answers a restaurant query with the city centroid. Those
# look plausible and are wrong, so only accept results that are actually a
# point of interest (or, for beaches, a natural feature).
POI_CATEGORIES = {"amenity", "shop", "leisure", "tourism", "natural",
                  "historic", "building", "club", "office"}
VAGUE_TYPES = {"city", "town", "village", "municipality", "hamlet", "state",
               "country", "county", "administrative", "suburb", "quarter",
               "neighbourhood", "city_district", "road", "residential",
               "postcode", "locality"}


def precise(res):
    cat = (res.get("category") or "").lower()
    atype = (res.get("addresstype") or res.get("type") or "").lower()
    if atype in VAGUE_TYPES:
        return False
    return cat in POI_CATEGORIES


def lookup(query):
    url = ENDPOINT + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    return data[0] if data else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--apply", action="store_true",
                    help="write results back into the file")
    args = ap.parse_args()

    doc = json.load(open(args.path, encoding="utf-8"))
    todo = [e for e in doc["places"] if e.get("_needs_geocode")]
    if not todo:
        print("nothing to geocode")
        return

    hits = 0
    for e in todo:
        key = e["name"].strip().lower()
        query = HINTS.get(key, e["name"])
        try:
            res = lookup(query)
        except Exception as exc:
            print(f"  !! {e['name']}: {exc}")
            time.sleep(1.1)
            continue
        if not res:
            print(f"  -- {e['name']}: no match")
            time.sleep(1.1)
            continue

        if not precise(res):
            print(f"  ~~ {e['name']}: only got {res.get('addresstype') or res.get('type')} "
                  f"\"{res.get('display_name','')[:60]}\" — too vague, skipped")
            time.sleep(1.1)
            continue

        lat, lon = float(res["lat"]), float(res["lon"])
        addr = res.get("address", {})
        city = (addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("municipality") or addr.get("suburb") or "")
        country = addr.get("country", "")
        region = addr.get("state", "")
        print(f"  ok {e['name']}")
        print(f"       -> {lat:.5f},{lon:.5f}  {res.get('display_name','')[:95]}")
        if args.apply:
            e["lat"], e["lng"] = round(lat, 6), round(lon, 6)
            if city:
                e["city"] = city
            if region:
                e["region"] = region
            if country:
                e["country"] = country
            e.pop("_needs_geocode", None)
            e["_geocoded"] = "nominatim"
        hits += 1
        time.sleep(1.1)

    print(f"\n{hits}/{len(todo)} resolved")
    if args.apply:
        with open(args.path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"written to {args.path}")
    else:
        print("(dry run — pass --apply to write)")


if __name__ == "__main__":
    main()
