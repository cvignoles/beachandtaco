# BeachAndTaco.com — Build Plan

## Stack

Plain HTML + CSS + Vanilla JS, deployed to Cloudflare Pages. No framework, no build step, no database. Fast, free to host, easy to edit.

## Site Structure

```
/
├── index.html          (Home + map)
├── blog/
│   └── index.html      (Coming Soon page + post template)
├── about.html
├── contact.html
├── css/
│   └── style.css
├── data/
│   └── places.json     (all beaches + taco spots — edit this to add a place)
├── js/
│   ├── map.js
│   ├── nav.js
│   └── config.js       (Maps browser key — committed; secured by referrer restriction)
└── images/
```

## Pages

- **Home** — banner, navigation, intro blurb, map, and "The Log" list of every spot
- **Blog** — "Coming Soon" page with a reusable post template for future use
- **About** — why BeachAndTaco.com, contact info
- **Contact** — submission form via Formspree (free tier, forwards to scavengeabout@gmail.com)

## Place Data — `data/places.json`

Places live in the repo as JSON, **not** in Google My Maps. Rationale:

- Google Maps *saved lists* have no public API and cannot be embedded as map layers, so the
  lists would have had to be rebuilt by hand in My Maps regardless.
- Keeping the data here means no second Google account owns it, and no KML caching delays.
- Each entry can carry a visit date, rating, notes, photo and blog link — a real log, not just
  pins. That drives the filterable list under the map and is indexable by search engines.

### Adding a place
Append an object to the `places` array in `data/places.json` and push. Cloudflare redeploys
automatically. No code changes.

```json
{
  "name": "Tacos El Gordo",
  "type": "taco",                    // "taco" or "beach"
  "lat": 32.6349, "lng": -117.0725,
  "city": "Chula Vista", "region": "California", "country": "United States",
  "visited": "2025-03-14",           // optional — sorts the list, newest first
  "rating": 5,                       // optional — 1-5
  "notes": "Adobada off the trompo. Cash only.",
  "mapsUrl": "https://maps.app.goo.gl/...",   // optional
  "photo": "images/places/el-gordo.jpg",      // optional
  "post": "blog/el-gordo.html"                // optional
}
```

Only `name`, `type`, `lat` and `lng` are required. Entries missing those are skipped.

## Map Behavior (`js/map.js`)

- Native `google.maps.Marker` pins, coral for tacos and teal for beaches, drawn as inline SVG.
- Click a pin for an info window with notes, rating, photo and links.
- Toggle buttons show/hide each type; a country dropdown filters further; "Show all on map"
  fits the viewport to everything currently visible.
- Geolocation on load: center on the user if granted, otherwise San Diego, CA.
- **The list and the map load independently.** If the Maps API is blocked, over quota or
  misconfigured, the map area shows a short message and the full log still renders below.

## Google Maps API Key

`js/config.js` **is committed on purpose.** A Maps JavaScript key is public by design — the
browser sends it to Google on every map load, so it is readable in DevTools no matter what.
Gitignoring it protected nothing and broke the deploy, since Cloudflare Pages builds from this
repo and the file would never reach the server.

Security comes from Google Cloud Console instead:

1. **Application restrictions → Websites:**
   - `https://beachandtaco.com/*`   (the bare apex — the wildcard below does NOT cover it)
   - `https://*.beachandtaco.com/*`
   - `http://localhost:8000/*`      (dev; no wildcard is allowed in the port position)
2. **API restrictions → Restrict key:** Maps JavaScript API only.
3. **Billing → Budgets & alerts:** a $5 budget on all services, as a backstop. A budget only
   notifies; for a hard stop set a daily quota cap on the Maps JavaScript API under Quotas.

Keys for server-side or one-off scripts (Places, Geocoding) must **not** be committed.

## Formspree Setup (Contact Form)

Yes, you need a free account. Steps:
1. Go to [formspree.io](https://formspree.io) and sign up
2. Create a new form, set the destination email to scavengeabout@gmail.com
3. Copy the form endpoint URL (looks like `https://formspree.io/f/xxxxxxxx`)
4. Paste it into `contact.html` as the form `action` attribute

## Migrating Your Saved Lists (one-time)

Source is the **personal** account; nothing needs to move to a second Google account.

1. Go to [takeout.google.com](https://takeout.google.com) signed in as the personal account.
2. Deselect all, then select **Saved** (your Maps lists). Export.
3. Each list arrives as a CSV of place names and Maps URLs.
4. A conversion script resolves each row to coordinates and writes `data/places.json`.
   Anything ambiguous gets flagged for manual confirmation.

Use a **separate, uncommitted** API key with the Places API enabled for that script, and
delete the key afterward.

## Cloudflare Pages Deployment

Domain `beachandtaco.com` is already registered and managed in Cloudflare.

### To connect the GitHub repo for auto-deploy:
1. Cloudflare Dashboard → **Pages** → **Create a project**
2. Choose **Connect to Git** → authorize GitHub → select the `beachandtaco` repo
3. Build settings: Framework = None, Build command = (leave blank), Output directory = `/` (root)
4. Click **Save and Deploy**

From that point on, every `git push` to `main` automatically deploys to beachandtaco.com.

## Visual Identity

- **Logo:** `/images/beachandtacoLogo.png`
- **Banner:** `/images/beachandtacowavebanner.png`
- **Palette:** retro beach — deep blue/purple, coral/pink, warm orange/yellow stripe (matching banner)
- **Tone:** friendly, casual, slightly nostalgic, surf/taco/travel vibe
- **Background:** white, clean layout with pastel beach color accents
- **Typography:** friendly + casual, modern enough for travel/food content
