// Global version injector for MSS pages
(function(){
  window.code_version = "5.5.3";
  async function resolveVersion(){
    try {
      const r = await fetch('http://localhost:5000/health');
      if (r.ok) {
        const j = await r.json();
        if (j && j.version) window.code_version = j.version;
      }
    } catch {}
  }
  function applyVersion(){
    const candidates = Array.from(document.querySelectorAll('#appVersion, .version, h1 span, h2 span, h3 span'));
    let updated = false;
    for (const el of candidates) {
      const txt = (el.textContent || '').trim();
      if (el.id === 'appVersion' || (el.classList && el.classList.contains('version')) || /^v/i.test(txt) || txt.length <= 10) {
        el.textContent = 'v' + window.code_version;
        updated = true;
      }
    }
    if (!updated) {
      const hdr = document.querySelector('h1, h2, h3');
      if (hdr) {
        const span = document.createElement('span');
        span.id = 'appVersion';
        span.style.fontSize = '14px';
        span.style.color = '#64748b';
        span.style.fontWeight = '400';
        span.style.marginLeft = '6px';
        span.textContent = 'v' + window.code_version;
        hdr.appendChild(document.createTextNode(' '));
        hdr.appendChild(span);
      }
    }
  }
  async function boot(){
    await resolveVersion();
    applyVersion();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
