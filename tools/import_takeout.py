#!/usr/bin/env python3
"""
Filter a Google Takeout Maps export down to beach- and taco-related places and
emit them in the data/places.json shape.

Usage:
    python3 tools/import_takeout.py ~/Downloads/Takeout [-o data/places.candidates.json]

Reads "Maps (your places)/Saved Places.json" and "Maps (your places)/Reviews.json"
if present, plus any custom-list CSVs under a top-level "Saved/" folder (that is
where Takeout puts named Maps lists such as "Beaches" and "Tacos").

Nothing is auto-trusted: every emitted entry carries `_match` explaining why it
was kept, so you can curate before merging into data/places.json.
"""

import argparse, csv, json, os, re, sys, urllib.parse as up

# --- Classification vocabulary -------------------------------------------------

TACO_WORDS = [
    "taco", "tacos", "takos", "taqueria", "taquería", "taqueiria",
    "birria", "al pastor", "adobada", "carnitas", "barbacoa",
    "mariscos", "cocina mexicana", "mexican", "mexicana", "mexicano",
    "torta", "tortas", "antojitos", "michoacan", "michoacán",
    "cenaduria", "cenaduría", "baja", "ensenada",
]
BEACH_WORDS = [
    "beach", "playa", "praia", "plage", "spiaggia", "strand", "playas",
    "surf", "malecon", "malecón", "seaside", "shoreline", "cove",
    "caleta", "costa", "coastal", "waterfront", "boardwalk", "pier",
]
# Words that, standing alone, are too weak to classify on their own.
WEAK = {"baja", "costa", "coastal", "mexican", "pier", "cove", "bay"}

# Names that look like a match but are not the thing itself. A place whose name
# says "deli" is a deli even if it sits in a town called Newport Beach.
NAME_BLOCKLIST = re.compile(
    r"\b(deli|delicatessen|market|dmv|auto care|sleepworld|bookstore|museum|"
    r"hotel|resort|condo|condos|airport|station|pharmacy|bank|dentist|clinic|"
    r"realty|rentals?|spa|gym)\b", re.I)


def classify(name, address, text):
    """Return (kind, [reasons]) where kind is 'taco', 'beach' or None."""
    hay = " ".join(x for x in (name, address, text) if x).lower()
    name_l = (name or "").lower()

    def hits(words):
        found = []
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", hay):
                strong = (w not in WEAK) and (w in name_l)
                found.append((w, strong))
        return found

    t, b = hits(TACO_WORDS), hits(BEACH_WORDS)
    t_strong = any(s for _, s in t)
    b_strong = any(s for _, s in b)

    # Drop weak-only evidence. "Baja" in a condo name or "Coastal" in a grill
    # name is not enough on its own — it produced false positives on real data.
    if t and all(w in WEAK for w, _ in t):
        t, t_strong = [], False
    if b and all(w in WEAK for w, _ in b):
        b, b_strong = [], False
    if not t and not b:
        return None, []

    # A strong name hit wins. Otherwise fall back to any hit at all.
    if t_strong and not b_strong:
        kind = "taco"
    elif b_strong and not t_strong:
        kind = "beach"
    elif t_strong and b_strong:
        kind = "taco"          # a taco place on a beach is still a taco entry
    elif t:
        kind = "taco"
    elif b:
        kind = "beach"
    else:
        return None, []

    # The blocklist always applies: a name that declares what the business is
    # beats a keyword picked up from its street address or town name.
    if NAME_BLOCKLIST.search(name or ""):
        return None, []

    reasons = [w for w, _ in (t if kind == "taco" else b)]
    return kind, reasons


# --- Readers -------------------------------------------------------------------

POSTAL = re.compile(r"^\s*(?:\d{4,6}(?:-\d{3,4})?|[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\s+", re.I)
US_STATE = re.compile(r"^([A-Z]{2})\s+\d{5}(?:-\d{4})?$")
# Short, dotted or well-known subdivisions that sit between city and country.
REGIONLIKE = re.compile(
    r"^(?:[A-Z]{2}|[A-Z][a-z]{0,3}\.|B\.C\.S?\.|[A-Z][a-zA-Z]*\.)$|"
    r"^(?:Jal|Gro|Guerrero|Jalisco|Baja California(?: Sur)?|Quintana Roo|"
    r"Nayarit|Sinaloa|Oaxaca|Yucat[aá]n|Sonora)$", re.I)


# Expand the abbreviations Google uses, to match the style of data/places.json.
REGION_FULL = {
    "CA": "California", "OR": "Oregon", "WA": "Washington", "NY": "New York",
    "NV": "Nevada", "AZ": "Arizona", "TX": "Texas", "FL": "Florida",
    "HI": "Hawaii", "MO": "Missouri", "MD": "Maryland", "VA": "Virginia",
    "GA": "Georgia", "DC": "District of Columbia",
    "Jal": "Jalisco", "B.C.S": "Baja California Sur", "BCS": "Baja California Sur",
    "B.C": "Baja California", "Gro": "Guerrero", "Q.R": "Quintana Roo",
    "Nay": "Nayarit", "Sin": "Sinaloa", "Son": "Sonora", "Oax": "Oaxaca",
}


def _region(r):
    return REGION_FULL.get(r, REGION_FULL.get(r.upper(), r))


def _clean(part):
    return POSTAL.sub("", part).strip()


def city_country(address):
    """Best-effort (city, region, country) from a Google-formatted address."""
    if not address:
        return "", "", ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) == 1:
        return "", "", parts[0]
    country = parts[-1]
    prev = parts[-2]

    m = US_STATE.match(prev)
    if m:                                   # "... , Chula Vista, CA 91910, USA"
        return (_clean(parts[-3]) if len(parts) >= 3 else ""), _region(m.group(1)), country
    if REGIONLIKE.match(prev) and len(parts) >= 3:
        return _clean(parts[-3]), _region(prev.rstrip(".")), country
    return _clean(prev), "", country


def from_geojson(path, source):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for feat in doc.get("features", []):
        p = feat.get("properties", {})
        loc = p.get("location") or {}
        name = loc.get("name") or ""
        url = p.get("google_maps_url", "")
        if not name:  # fall back to the ?q= term
            name = up.parse_qs(up.urlparse(url).query).get("q", [""])[0]
        address = loc.get("address", "")
        text = p.get("review_text_published", "") or ""
        kind, why = classify(name, address, text)
        if not kind:
            continue
        lon, lat = (feat.get("geometry", {}).get("coordinates") or [0, 0])[:2]
        city, region, country = city_country(address)
        entry = {
            "name": name,
            "type": kind,
            "lat": round(lat, 6),
            "lng": round(lon, 6),
            "city": city,
            "country": country,
            "notes": text.strip(),
            "mapsUrl": url,
            "_match": ", ".join(why),
            "_source": source,
        }
        if region:
            entry["region"] = region
        if p.get("five_star_rating_published"):
            entry["rating"] = p["five_star_rating_published"]
        if p.get("date"):
            entry["visited"] = p["date"][:10]
        if [lon, lat] == [0, 0]:
            entry["_needs_geocode"] = True
        out.append(entry)
    return out


def from_list_csvs(saved_dir):
    """Takeout puts named Maps lists (e.g. Beaches.csv, Tacos.csv) under Saved/."""
    out = []
    if not os.path.isdir(saved_dir):
        return out
    for fn in sorted(os.listdir(saved_dir)):
        if not fn.lower().endswith(".csv"):
            continue
        listname = os.path.splitext(fn)[0]
        low = listname.lower()
        forced = "taco" if "taco" in low else "beach" if "beach" in low else None
        with open(os.path.join(saved_dir, fn), encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("Title") or row.get("title") or "").strip()
                url = (row.get("URL") or row.get("url") or "").strip()
                note = (row.get("Note") or row.get("note") or "").strip()
                if not name:
                    continue
                kind = forced or classify(name, "", note)[0]
                if not kind:
                    continue
                out.append({
                    "name": name, "type": kind,
                    "lat": 0, "lng": 0, "city": "", "country": "",
                    "notes": note, "mapsUrl": url,
                    "_match": f"list:{listname}", "_source": f"Saved/{fn}",
                    "_needs_geocode": True,
                })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("takeout", help="path to the unzipped Takeout folder")
    ap.add_argument("-o", "--out", default="data/places.candidates.json")
    args = ap.parse_args()

    root = os.path.expanduser(args.takeout)
    places_dir = os.path.join(root, "Maps (your places)")
    found = []
    found += from_geojson(os.path.join(places_dir, "Saved Places.json"), "Saved Places")
    found += from_geojson(os.path.join(places_dir, "Reviews.json"), "Reviews")
    found += from_list_csvs(os.path.join(root, "Saved"))

    # De-duplicate on rounded coordinates, else on lowercased name.
    seen, uniq = {}, []
    for e in found:
        key = (round(e["lat"], 4), round(e["lng"], 4)) if e["lat"] or e["lng"] \
              else ("name", e["name"].lower())
        if key in seen:
            # Prefer the record that has notes/rating.
            if len(json.dumps(e)) > len(json.dumps(seen[key])):
                uniq[uniq.index(seen[key])] = e
                seen[key] = e
            continue
        seen[key] = e
        uniq.append(e)

    uniq.sort(key=lambda e: (e["type"], e["name"].lower()))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"places": uniq}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    tacos = sum(1 for e in uniq if e["type"] == "taco")
    beaches = len(uniq) - tacos
    nogeo = sum(1 for e in uniq if e.get("_needs_geocode"))
    print(f"{len(uniq)} candidates -> {args.out}")
    print(f"  tacos:   {tacos}")
    print(f"  beaches: {beaches}")
    if nogeo:
        print(f"  {nogeo} need coordinates filled in")


if __name__ == "__main__":
    main()
