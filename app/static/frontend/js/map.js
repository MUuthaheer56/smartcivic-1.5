// Global Leaflet map utility scripts
function initializeMap(containerId, lat = 12.9716, lng = 77.5946, zoom = 13) {
  const map = L.map(containerId).setView([lat, lng], zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  return map;
}

// Marker style status configuration mapping
const STATUS_COLORS = {
  'REPORTED': 'red',
  'VERIFIED': 'orange',
  'ASSIGNED': 'blue',
  'IN_PROGRESS': 'yellow',
  'RESOLVED': 'green',
  'REOPENED': 'purple',
  'REJECTED': 'black'
};

function getMarkerIcon(status) {
  const color = STATUS_COLORS[status] || 'blue';
  return L.icon({
    iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  });
}
