const CPCB = {
  residential: [55, 45],
  commercial:  [65, 55],
  industrial:  [75, 70],
  silence:     [50, 40]
};

async function recordNoise(zone = "residential", durationMs = 10000) {
  const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ctx      = new AudioContext();
  const src      = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  src.connect(analyser);

  const samples = [];
  const buf     = new Float32Array(analyser.fftSize);
  const id      = setInterval(() => {
    analyser.getFloatTimeDomainData(buf);
    const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length);
    samples.push(rms);
  }, 100);

  await new Promise(r => setTimeout(r, durationMs));
  clearInterval(id);
  stream.getTracks().forEach(t => t.stop());

  const avg  = samples.reduce((a, b) => a + b, 0) / (samples.length || 1);
  const db   = avg > 0 ? 20 * Math.log10(avg / 0.00002) : 0;
  const dbC  = Math.max(30, Math.min(120, db));
  const hour = new Date().getHours();
  const isDay = hour >= 6 && hour < 22;
  const [dl, nl] = CPCB[zone] || CPCB.residential;
  const limit    = isDay ? dl : nl;

  return {
    measured_db:    Math.round(dbC),
    legal_limit_db: limit,
    zone,
    period:         isDay ? "day" : "night",
    is_violation:   dbC > limit,
    excess_db:      Math.max(0, Math.round(dbC - limit))
  };
}
