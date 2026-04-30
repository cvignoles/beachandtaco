// Replace these with your Google My Maps KML URLs once you create the map.
// Steps: mymaps.google.com → Create map → Share (make public) → copy the map ID from the URL
// KML URL format: https://www.google.com/maps/d/kml?forcekml=1&mid=YOUR_MAP_ID
const TACOS_KML_URL   = null; // e.g. 'https://www.google.com/maps/d/kml?forcekml=1&mid=1aBcDeFgHiJkLmNoPqRsTuVwXyZ'
const BEACHES_KML_URL = null;

const SAN_DIEGO = { lat: 32.7157, lng: -117.1611 };

let map;
let tacosLayer   = null;
let beachesLayer = null;
let tacosVisible   = true;
let beachesVisible = true;

function initMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 10,
    center: SAN_DIEGO,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    styles: mapStyles,
  });

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => map.setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {} // denied — stay on San Diego
    );
  }

  if (TACOS_KML_URL) {
    tacosLayer = new google.maps.KmlLayer({
      url: TACOS_KML_URL,
      map: map,
      preserveViewport: true,
    });
  }

  if (BEACHES_KML_URL) {
    beachesLayer = new google.maps.KmlLayer({
      url: BEACHES_KML_URL,
      map: map,
      preserveViewport: true,
    });
  }

  document.getElementById('btn-tacos').addEventListener('click',   () => toggleLayer('tacos'));
  document.getElementById('btn-beaches').addEventListener('click', () => toggleLayer('beaches'));
}

function toggleLayer(layer) {
  const btn = document.getElementById('btn-' + layer);
  if (layer === 'tacos') {
    tacosVisible = !tacosVisible;
    if (tacosLayer) tacosLayer.setMap(tacosVisible ? map : null);
    btn.classList.toggle('off', !tacosVisible);
  } else {
    beachesVisible = !beachesVisible;
    if (beachesLayer) beachesLayer.setMap(beachesVisible ? map : null);
    btn.classList.toggle('off', !beachesVisible);
  }
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

// Load the Maps JS API dynamically using the key from config.js
(function () {
  const script = document.createElement('script');
  script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_API_KEY}&callback=initMap`;
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
})();
