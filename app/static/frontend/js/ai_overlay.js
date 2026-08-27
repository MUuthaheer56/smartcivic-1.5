// Draws YOLO bounding box on the complaint photo canvas
function drawBoundingBox(canvasId, bbox, label, confidence) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const img = canvas.previousElementSibling; // <img> must be sibling

  // Adjust canvas size to match the displayed image size
  canvas.width = img.clientWidth;
  canvas.height = img.clientHeight;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Calculate scaling factors between original image and displayed image
  const scaleX = canvas.width / img.naturalWidth;
  const scaleY = canvas.height / img.naturalHeight;

  const x = bbox.x1 * scaleX;
  const y = bbox.y1 * scaleY;
  const w = (bbox.x2 - bbox.x1) * scaleX;
  const h = (bbox.y2 - bbox.y1) * scaleY;

  ctx.strokeStyle = "#EF4444";
  ctx.lineWidth   = 3;
  ctx.strokeRect(x, y, w, h);

  ctx.fillStyle = "#EF4444";
  ctx.fillRect(x, y - 24, 220, 24);
  ctx.fillStyle = "#FFFFFF";
  ctx.font      = "14px Inter, sans-serif";
  ctx.fillText(`${label} — ${(confidence * 100).toFixed(1)}%`, x + 6, y - 6);
}

// Called after AI analysis returns from server
function renderAIResult(result) {
  if (!result || result.status !== "PROCESSED") return;

  const detClass = result.ai_detected_class;
  const conf     = result.ai_confidence;
  const bbox     = result.bounding_box;
  const severity = result.severity_score;

  document.getElementById("ai-class").textContent    = detClass || "None detected";
  document.getElementById("ai-confidence").textContent = conf ? `${(conf * 100).toFixed(1)}%` : "—";
  document.getElementById("ai-severity").textContent  = severity ? `${severity}/10` : "—";
  document.getElementById("ai-routing").textContent   = result.routing_status || "—";

  if (bbox && detClass) {
    // Wait a brief moment for layout/display rendering of image size to anchor coordinates
    setTimeout(() => {
      drawBoundingBox("ai-canvas", bbox, detClass, conf);
    }, 100);
  }

  if (result.is_duplicate) {
    document.getElementById("duplicate-warning").style.display = "block";
    document.getElementById("duplicate-id").textContent = result.duplicate_of;
  }
}
