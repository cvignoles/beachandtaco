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
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json?"
FIELDS = ("places.displayName,places.formattedAddress,places.location,"
          "places.googleMapsUri,places.rating")


class ApiError(RuntimeError):
    pass


def _detail(exc):
    """Google puts the real reason in the response body, not the status line."""
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:
        return str(exc)
    try:
        j = json.loads(body)
        err = j.get("error", j)
        msg = err.get("message") or err.get("error_message") or ""
        status = err.get("status", "")
        details = err.get("details") or []
        reasons = ", ".join(
            d.get("reason", "") for d in details if isinstance(d, dict) and d.get("reason"))
        return " | ".join(x for x in (status, msg, reasons) if x) or body[:400]
    except Exception:
        return body[:400]


def search_places(query, key):
    """Places API (New). Requires the 'Places API (New)' SKU, not the legacy one."""
    body = json.dumps({"textQuery": query, "maxResultCount": 1}).encode()
    req = urllib.request.Request(PLACES_ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELDS,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.load(r)
    except urllib.error.HTTPError as exc:
        raise ApiError(f"HTTP {exc.code}: {_detail(exc)}") from None
    places = out.get("places") or []
    if not places:
        return None
    p = places[0]
    return {
        "lat": p["location"]["latitude"],
        "lng": p["location"]["longitude"],
        "address": p.get("formattedAddress", ""),
        "url": p.get("googleMapsUri", ""),
        "via": "places",
    }


def search_geocoding(query, key):
    """Geocoding API fallback. Weaker on business names, but widely enabled."""
    url = GEOCODE_ENDPOINT + urllib.parse.urlencode({"address": query, "key": key})
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            out = json.load(r)
    except urllib.error.HTTPError as exc:
        raise ApiError(f"HTTP {exc.code}: {_detail(exc)}") from None
    status = out.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        raise ApiError(f"{status}: {out.get('error_message', '')}")
    r0 = out["results"][0]
    loc = r0["geometry"]["location"]
    # A rooftop/POI hit is trustworthy; a city-level one is not.
    loose = r0["geometry"].get("location_type") == "APPROXIMATE"
    types = set(r0.get("types", []))
    if loose and types & {"locality", "political", "administrative_area_level_1",
                          "administrative_area_level_2", "country", "postal_code"}:
        return None
    return {
        "lat": loc["lat"],
        "lng": loc["lng"],
        "address": r0.get("formatted_address", ""),
        "url": "",
        "via": "geocoding",
    }


def search(query, key, mode):
    if mode == "geocoding":
        return search_geocoding(query, key)
    if mode == "places":
        return search_places(query, key)
    # auto: try Places, fall back to Geocoding if Places is not usable.
    try:
        return search_places(query, key)
    except ApiError as exc:
        print(f"     Places API unavailable ({exc}); falling back to Geocoding API")
        return search_geocoding(query, key)


# Reuse the address parser from the importer rather than keeping a second,
# weaker copy here. The local one returned "Nay." as the city for Sayulita.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_takeout import city_country as split_address  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mode", choices=["auto", "places", "geocoding"], default="auto",
                    help="which Google API to use (default: try Places, then Geocoding)")
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
    failures = 0
    for e in todo:
        # Any city already parsed off the source record sharpens the query.
        q = " ".join(x for x in (e["name"], e.get("city"), e.get("country")) if x)
        try:
            res = search(q, key, args.mode)
        except ApiError as exc:
            print(f"  !! {e['name']}: {exc}")
            failures += 1
            if failures == 1:
                print(TROUBLESHOOT)
            if failures >= 3:
                print("\nStopping after 3 consecutive API errors — fix the key first.")
                break
            continue
        except Exception as exc:
            print(f"  !! {e['name']}: {exc}")
            continue
        failures = 0
        if not res:
            print(f"  -- {e['name']}: no confident match")
            continue
        addr = res["address"]
        print(f"  ok {e['name']}  [{res['via']}]")
        print(f"       -> {res['lat']:.5f},{res['lng']:.5f}  {addr[:80]}")
        if args.apply:
            city, region, country = split_address(addr)
            e["lat"] = round(res["lat"], 6)
            e["lng"] = round(res["lng"], 6)
            e["city"] = city or e.get("city", "")
            if region:
                e["region"] = region
            e["country"] = country or e.get("country", "")
            if res.get("url"):
                e["mapsUrl"] = res["url"]
            e["_address"] = addr
            e.pop("_needs_geocode", None)
            e["_geocoded"] = "google-" + res["via"]
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
