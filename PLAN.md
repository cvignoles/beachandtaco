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
├── js/
│   ├── map.js
│   └── config.js       (API key — gitignored, never committed)
└── images/
```

## Pages

- **Home** — banner, navigation, intro blurb, embedded Google Map
- **Blog** — "Coming Soon" page with a reusable post template for future use
- **About** — why BeachAndTaco.com, contact info
- **Contact** — submission form via Formspree (free tier, forwards to scavengeabout@gmail.com)

## Google Maps Integration

Using **Google My Maps** (mymaps.google.com) with two layers: "Beaches" and "Tacos".

- Create the My Maps map after the rest of the site is done
- Make the map public, then the site loads it via a KML layer
- Add new places by adding a pin in My Maps — no code changes needed

### Geolocation behavior
- On page load, request geolocation permission
- If granted: center map on user's location
- If denied: center on San Diego, CA

### Toggling layers
Two toggle buttons on the map: "Taco Spots" and "Beaches" — each shows/hides that layer.

## Google Maps API Key

- Key is restricted to `*.beachandtaco.com/*` (add `localhost` for local dev)
- Stored in `js/config.js` which is listed in `.gitignore` — never committed to GitHub
- Industry-standard approach for static sites: domain restriction enforced server-side by Google

**To do:** Add `localhost` as an allowed referrer in Google Cloud Console → APIs & Services → Credentials → your Maps key.

## Formspree Setup (Contact Form)

Yes, you need a free account. Steps:
1. Go to [formspree.io](https://formspree.io) and sign up
2. Create a new form, set the destination email to scavengeabout@gmail.com
3. Copy the form endpoint URL (looks like `https://formspree.io/f/xxxxxxxx`)
4. Paste it into `contact.html` as the form `action` attribute

## Transferring Google Maps Data to My Maps

One-time migration from your personal account to scavengeabout@gmail.com:

1. Open Google Maps on desktop → Your places → Lists (Beaches / Tacos)
2. Log into [mymaps.google.com](https://mymaps.google.com) as scavengeabout@gmail.com
3. Create a new map, add two layers: rename them "Beaches" and "Tacos"
4. Use the My Maps search bar to find and add each place from your saved lists
5. Make the map **Public** (Share → Anyone with the link)

Going forward: manage everything in My Maps. No code changes needed to add new spots.

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

## Model Choice

**Sonnet 4.6** is the right choice for this project. This is HTML, CSS, and JavaScript work — Opus 4.7 costs ~5x more per token with no meaningful quality difference for web development. Opus 4.7 is better suited to complex multi-step reasoning and research-heavy tasks, not building static websites.
