// General complaint client side forms utilities
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("complaint-form");
  if (!form) return;

  // Track coordinates selection helper pings
  const latInput = document.getElementById("lat");
  const lngInput = document.getElementById("lng");

  if (latInput && lngInput && !latInput.value) {
    // Fill default values if empty to guide coordinate selection
    latInput.value = "12.9716";
    lngInput.value = "77.5946";
  }
});
