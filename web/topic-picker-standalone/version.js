// Global version injector for MSS pages
// Version: 5.5.8 - Fixed CSP issue by always using same origin
(function(){
  window.code_version = "5.6.9";
  async function resolveVersion(){
    try {
      // CRITICAL: Always use same origin - NEVER hardcode localhost
      // This works for both localhost (development) and production (Cloud Run)
      // Using window.location.origin ensures CSP compliance
      const apiBase = window.location.origin;
      
      // Double-check we're not using localhost (safety check)
      if (apiBase.includes('localhost:5000') || apiBase.includes('127.0.0.1:5000')) {
        // This is development - that's fine, but log it for debugging
        console.debug('[version.js] Using localhost for version check (dev mode)');
      }
      
      const r = await fetch(`${apiBase}/health`, { 
        cache: 'no-store',
        mode: 'cors',
        credentials: 'omit'
      });
      if (r.ok) {
        const j = await r.json();
        if (j && j.version) window.code_version = j.version;
      }
    } catch (e) {
      // Silently fail - version check is optional
      // Don't log errors to avoid console noise
    }
  }
  function applyVersion(){
    const candidates = Array.from(document.querySelectorAll('#appVersion, .version, h1 span, h2 span, h3 span'));
    let updated = false;
    for (const el of candidates) {
      // Skip elements or their parents with data-no-version attribute
      if (el.hasAttribute('data-no-version') || el.parentElement?.hasAttribute('data-no-version')) {
        continue;
      }
      // Skip spans with IDs other than appVersion (like platformTitle, etc)
      if (el.id && el.id !== 'appVersion') {
        continue;
      }
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
