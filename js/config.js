// Google Maps browser key.
//
// This file IS committed, on purpose. A Maps JavaScript key is public by design:
// the browser sends it to Google on every map load, so it is visible in DevTools
// whether or not it lives in git. Hiding it here protected nothing and broke the
// deploy, because Cloudflare Pages builds from this repo.
//
// It is secured in Google Cloud Console by:
//   - HTTP referrer restriction (beachandtaco.com + localhost only)
//   - API restriction (Maps JavaScript API only)
//   - a billing budget alert as a backstop
//
// Do NOT put server-side or script keys (Places, Geocoding) in this file.
const MAPS_API_KEY = 'AIzaSyBq0FQhDd7Seo95k1Cwd5NFHHJAfLkVEZo';
