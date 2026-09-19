// BeachAndTaco.com map — renders places from data/places.json as native markers.
// To add a place: append an entry to data/places.json and push. No code changes needed.

const SAN_DIEGO = { lat: 32.7157, lng: -117.1611 };
const DATA_URL  = 'data/places.json';

const TYPE_META = {
  taco:  { label: 'Taco Spot', color: '#FF5A5F', emoji: '\u{1F32E}' },
  beach: { label: 'Beach',     color: '#00B4D8', emoji: '\u{1F3D6}️' },
};

let map;
let infoWindow;
let places = [];                 // raw entries from JSON, each given an `id`
const markers = new Map();       // id -> google.maps.Marker
const visible = { taco: true, beach: true };
let countryFilter = 'all';

// ---------- Bootstrap ----------
//
// The list and the map load independently. If the Google Maps API is blocked,
// over quota, or misconfigured, the log below the map still renders.

let placesReady;   // resolves once data/places.json has been parsed

document.addEventListener('DOMContentLoaded', () => {
  wireControls();
  placesReady = loadPlaces();
});

function wireControls() {
  document.getElementById('btn-tacos').addEventListener('click',   () => toggleType('taco',  'btn-tacos'));
  document.getElementById('btn-beaches').addEventListener('click', () => toggleType('beach', 'btn-beaches'));
  document.getElementById('btn-show-all').addEventListener('click', fitAllVisible);
  document.getElementById('country-filter').addEventListener('change', (e) => {
    countryFilter = e.target.value;
    applyFilters();
  });
}

async function loadPlaces() {
  try {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    places = (data.places || [])
      .filter((p) => TYPE_META[p.type] && isFinite(p.lat) && isFinite(p.lng))
      .map((p, i) => ({ ...p, id: i }));
  } catch (err) {
    console.error('Could not load places:', err);
    document.getElementById('place-list').innerHTML =
      '<p class="list-empty">Could not load the spots. Try refreshing.</p>';
    return;
  }
  buildCountryFilter();
  renderList();
}

// Called by the Google Maps API once it finishes loading.
async function initMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 10,
    center: SAN_DIEGO,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    styles: mapStyles,
  });
  infoWindow = new google.maps.InfoWindow();

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => map.setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {} // denied — stay on San Diego
    );
  }

  await placesReady;          // markers need the data
  places.forEach(createMarker);
  applyFilters();
}

function mapFailed(msg) {
  console.error(msg);
  const el = document.getElementById('map');
  if (el) el.innerHTML = '<p class="map-error">The map could not load, but the full list of spots is below.</p>';
}

// ---------- Markers ----------

function markerIcon(type) {
  const { color } = TYPE_META[type];
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="36" height="46" viewBox="0 0 36 46">
      <path d="M18 1C8.6 1 1 8.6 1 18c0 12.4 17 27 17 27s17-14.6 17-27C35 8.6 27.4 1 18 1z"
            fill="${color}" stroke="#ffffff" stroke-width="2"/>
      <circle cx="18" cy="18" r="7" fill="#ffffff"/>
    </svg>`;
  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(36, 46),
    anchor: new google.maps.Point(18, 45),
  };
}

function createMarker(place) {
  const marker = new google.maps.Marker({
    position: { lat: place.lat, lng: place.lng },
    map,
    title: place.name,
    icon: markerIcon(place.type),
  });
  marker.addListener('click', () => openPlace(place.id, false));
  markers.set(place.id, marker);
}

function openPlace(id, pan) {
  const place = places[id];
  const marker = markers.get(id);
  if (!place || !marker) return;
  if (pan) {
    map.panTo(marker.getPosition());
    if (map.getZoom() < 12) map.setZoom(13);
  }
  infoWindow.setContent(infoContent(place));
  infoWindow.open({ map, anchor: marker });
  highlightCard(id);
}

// ---------- Filtering ----------

function isShown(place) {
  return visible[place.type] && (countryFilter === 'all' || place.country === countryFilter);
}

function applyFilters() {
  places.forEach((p) => {
    const m = markers.get(p.id);
    if (m) m.setVisible(isShown(p));
  });
  renderList();
}

function toggleType(type, btnId) {
  visible[type] = !visible[type];
  document.getElementById(btnId).classList.toggle('off', !visible[type]);
  if (infoWindow) infoWindow.close();
  applyFilters();
}

function buildCountryFilter() {
  const select = document.getElementById('country-filter');
  const countries = [...new Set(places.map((p) => p.country).filter(Boolean))].sort();
  countries.forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    select.appendChild(opt);
  });
}

function fitAllVisible() {
  if (!map) return;
  const shown = places.filter(isShown);
  if (!shown.length) return;
  const bounds = new google.maps.LatLngBounds();
  shown.forEach((p) => bounds.extend({ lat: p.lat, lng: p.lng }));
  map.fitBounds(bounds, 60);
  if (shown.length === 1) map.setZoom(13);
}

// ---------- List under the map ----------

function renderList() {
  const container = document.getElementById('place-list');
  const shown = places
    .filter(isShown)
    .sort((a, b) => (b.visited || '').localeCompare(a.visited || '') || a.name.localeCompare(b.name));

  document.getElementById('list-count').textContent =
    shown.length === 1 ? '1 spot' : `${shown.length} spots`;

  if (!shown.length) {
    container.innerHTML = '<p class="list-empty">Nothing matches these filters yet.</p>';
    return;
  }

  container.innerHTML = shown.map(cardHTML).join('');
  container.querySelectorAll('.place-card').forEach((card) => {
    card.addEventListener('click', () => {
      if (!map) return;
      openPlace(Number(card.dataset.id), true);
      document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
}

function cardHTML(p) {
  const meta = TYPE_META[p.type];
  const where = [p.city, p.region, p.country].filter(Boolean).join(', ');
  return `
    <article class="place-card type-${p.type}" data-id="${p.id}" tabindex="0">
      ${p.photo ? `<img class="card-photo" src="${esc(p.photo)}" alt="${esc(p.name)}" loading="lazy">` : ''}
      <div class="card-body">
        <div class="card-top">
          <span class="type-badge" style="background:${meta.color}">${meta.emoji} ${meta.label}</span>
          ${p.rating ? `<span class="stars" aria-label="${p.rating} out of 5">${stars(p.rating)}</span>` : ''}
        </div>
        <h3>${esc(p.name)}</h3>
        <p class="card-where">${esc(where)}</p>
        ${p.notes ? `<p class="card-notes">${esc(p.notes)}</p>` : ''}
        <p class="card-foot">
          ${p.visited ? `<span>Visited ${fmtDate(p.visited)}</span>` : '<span></span>'}
          ${p.post ? `<a href="${esc(p.post)}" onclick="event.stopPropagation()">Read the story</a>` : ''}
        </p>
      </div>
    </article>`;
}

function infoContent(p) {
  const meta = TYPE_META[p.type];
  const where = [p.city, p.country].filter(Boolean).join(', ');
  return `
    <div class="iw">
      ${p.photo ? `<img class="iw-photo" src="${esc(p.photo)}" alt="${esc(p.name)}">` : ''}
      <span class="type-badge" style="background:${meta.color}">${meta.emoji} ${meta.label}</span>
      <h3 class="iw-title">${esc(p.name)}</h3>
      <p class="iw-where">${esc(where)}${p.rating ? ` &middot; <span class="stars">${stars(p.rating)}</span>` : ''}</p>
      ${p.notes ? `<p class="iw-notes">${esc(p.notes)}</p>` : ''}
      <p class="iw-links">
        ${p.mapsUrl ? `<a href="${esc(p.mapsUrl)}" target="_blank" rel="noopener">Open in Google Maps</a>` : ''}
        ${p.post ? `<a href="${esc(p.post)}">Read the story</a>` : ''}
      </p>
    </div>`;
}

function highlightCard(id) {
  document.querySelectorAll('.place-card.active').forEach((c) => c.classList.remove('active'));
  const card = document.querySelector(`.place-card[data-id="${id}"]`);
  if (card) card.classList.add('active');
}

// ---------- Helpers ----------

function stars(n) {
  n = Math.max(0, Math.min(5, Math.round(n)));
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

function fmtDate(iso) {
  const d = new Date(iso + 'T00:00:00');
  return isNaN(d) ? iso : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const mapStyles = [
  { featureType: 'water',               elementType: 'geometry',        stylers: [{ color: '#0096c7' }] },
  { featureType: 'water',               elementType: 'labels.text.fill', stylers: [{ color: '#ffffff' }] },
  { featureType: 'landscape.natural',   elementType: 'geometry',        stylers: [{ color: '#f5ead6' }] },
  { featureType: 'poi.park',            elementType: 'geometry',        stylers: [{ color: '#a8d5a2' }] },
  { featureType: 'road',                elementType: 'geometry',        stylers: [{ color: '#ffffff' }] },
  { featureType: 'road',                elementType: 'geometry.stroke', stylers: [{ color: '#e0d6c2' }] },
  { featureType: 'administrative',      elementType: 'geometry.stroke', stylers: [{ color: '#c9b8a8' }] },
];

// Load the Maps JS API using the key from config.js
(function () {
  if (typeof MAPS_API_KEY === 'undefined' || !MAPS_API_KEY) {
    document.addEventListener('DOMContentLoaded', () => mapFailed('MAPS_API_KEY is missing — check js/config.js'));
    return;
  }
  const script = document.createElement('script');
  script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_API_KEY}&callback=initMap&loading=async`;
  script.async = true;
  script.defer = true;
  script.onerror = () => mapFailed('Google Maps API failed to load.');
  document.head.appendChild(script);

  // Surface auth/referrer failures (Google calls this global on key rejection).
  window.gm_authFailure = () => mapFailed('Google Maps rejected the API key — check the referrer restrictions.');
})();
