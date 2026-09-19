#!/usr/bin/env python3
"""
Resolve the remaining `_needs_geocode` entries with the Google Places API.

These places came out of Google Maps, so Google resolves them far more
accurately than OpenStreetMap does — Nominatim answers a restaurant query with
the city centroid, which looks plausible and is wrong.

    export GOOGLE_PLACES_KEY=...        # a TEMPORARY, UNRESTRICTED key
    python3 tools/geocode_google.py data/places.candidates.json --apply

Important: your site key is referrer-restricted, which rejects server-side
calls like these. Make a second key, enable ONLY "Places API (New)" on it,
run this once, then DELETE it. Never commit it.

Cost: Text Search is billed per request. Ten lookups is far inside the free
monthly allowance, but the key should still be deleted afterward.
"""
import argparse, json, os, sys, time, urllib.request

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.displayName,places.formattedAddress,places.location,"
          "places.googleMapsUri,places.rating")


def search(query, key):
    body = json.dumps({"textQuery": query, "maxResultCount": 1}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELDS,
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    places = out.get("places") or []
    return places[0] if places else None


def split_address(addr):
    parts = [p.strip() for p in (addr or "").split(",") if p.strip()]
    if len(parts) < 2:
        return "", "", ""
    country = parts[-1]
    prev = parts[-2]
    bits = prev.split()
    if len(bits) == 2 and len(bits[0]) == 2 and bits[0].isupper():
        return (parts[-3] if len(parts) >= 3 else ""), bits[0], country
    return prev, "", country


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GOOGLE_PLACES_KEY")
    if not key:
        sys.exit("Set GOOGLE_PLACES_KEY to a temporary, unrestricted Places API key.")

    doc = json.load(open(args.path, encoding="utf-8"))
    todo = [e for e in doc["places"] if e.get("_needs_geocode")]
    if not todo:
        print("nothing to resolve")
        return

    done = 0
    for e in todo:
        # Any city already parsed off the source record sharpens the query.
        q = " ".join(x for x in (e["name"], e.get("city"), e.get("country")) if x)
        try:
            res = search(q, key)
        except Exception as exc:
            print(f"  !! {e['name']}: {exc}")
            continue
        if not res:
            print(f"  -- {e['name']}: no match")
            continue
        loc = res["location"]
        addr = res.get("formattedAddress", "")
        print(f"  ok {e['name']}")
        print(f"       -> {loc['latitude']:.5f},{loc['longitude']:.5f}  {addr[:80]}")
        if args.apply:
            city, region, country = split_address(addr)
            e["lat"] = round(loc["latitude"], 6)
            e["lng"] = round(loc["longitude"], 6)
            e["city"] = city or e.get("city", "")
            if region:
                e["region"] = region
            e["country"] = country or e.get("country", "")
            if res.get("googleMapsUri"):
                e["mapsUrl"] = res["googleMapsUri"]
            e.pop("_needs_geocode", None)
            e["_geocoded"] = "google-places"
        done += 1
        time.sleep(0.2)

    print(f"\n{done}/{len(todo)} resolved")
    if args.apply:
        with open(args.path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"written to {args.path}")
    else:
        print("(dry run — pass --apply to write)")


if __name__ == "__main__":
    main()
