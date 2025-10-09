async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => (e[k] = v));
  children.forEach((c) => e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
  return e;
}

async function main() {
  const API_BASE = 'http://localhost:5000';
  const GEN_KEY = 'mss_tp_topics';
  const PROMPT_KEY = 'mss_tp_prompt';
  const DEFAULT_PROMPT = `Generate 5 timely, SEO-friendly YouTube video topics for the brand "{{brand}}".
- Mix evergreen and trending angles.
- Keep titles concise and compelling (max ~70 chars).
- Provide a one-line angle/hook, and 5-10 keywords per topic.
Return JSON only: [{ title, angle, keywords[] }].`;

  const $base = document.getElementById('base');
  const $brand = document.getElementById('brand');
  const $seed = document.getElementById('seed');
  const $prompt = document.getElementById('topicsPrompt');
  const $btn = document.getElementById('btnFetch');
  const $btnClear = document.getElementById('btnClear');
  const $wrap = document.getElementById('topics');
  const $status = document.getElementById('status');
  const $genMeta = document.getElementById('genMeta');

  // Restore prompt
  if ($prompt) {
    try {
      const saved = (localStorage.getItem(PROMPT_KEY) || '').trim();
      $prompt.value = saved || DEFAULT_PROMPT.replace('{{brand}}', ($brand.value || 'Many Sources Say'));
      $prompt.addEventListener('input', () => { try { localStorage.setItem(PROMPT_KEY, $prompt.value); } catch {} });
    } catch {}
  }

  function renderList(list) {
    $wrap.innerHTML = '';
    list.forEach((t, idx) => {
      const card = el('div', { className: 'card' }, [
        el('div', { className: 'title' }, [document.createTextNode(`${idx + 1}. ${t.yt_title || t.title}`)]),
        el('div', { className: 'muted' }, [document.createTextNode(t.angle || '')]),
        el('div', {}, [
          el('button', {
            innerText: 'Use in Notebook',
            style: 'background:#10b981; border-color:#10b981;',
            onclick: async () => {
              try {
                try { localStorage.setItem('editingTopic', JSON.stringify(t)); } catch {}
                try { await fetch(`${API_BASE}/set-selected-topic`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(t) }); } catch {}
                window.location.href = '../topic-picker-standalone/notebooklm.html';
              } catch (e) { $status.textContent = `Error: ${e.message}`; }
            }
          })
        ])
      ]);
      $wrap.appendChild(card);
    });
  }

  $btn.onclick = async () => {
    try {
      $status.textContent = 'Fetching topics...';
      $wrap.innerHTML = '';
      const baseInput = ($base && $base.value ? $base.value : API_BASE).replace(/\/$/, '');
      const payload = { brand: $brand.value || 'Many Sources Say', seed: $seed.value || '', limit: 5 };
      const prompt = ($prompt && $prompt.value && $prompt.value.trim()) ? $prompt.value.trim() : '';
      if (prompt) payload.prompt = prompt;
      let data;
      if (/localhost:5000|127\.0\.0\.1:5000/.test(baseInput)) {
        let resp = await fetch(`${API_BASE}/generate-topics`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        if (!resp.ok && resp.status === 405) {
          const qs = new URLSearchParams({ brand: payload.brand, seed: payload.seed, limit: String(payload.limit) });
          if (prompt) qs.set('prompt', prompt);
          resp = await fetch(`${API_BASE}/generate-topics?${qs.toString()}`);
        }
        if (!resp.ok) throw new Error(await resp.text());
        data = await resp.json();
      } else {
        data = await fetchJSON(`${baseInput}/webhook-test/topics-ideation`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      }
      const topics = (data.topics || []).slice(0, 5);
      if (!topics.length) throw new Error('No topics returned');
      try { localStorage.setItem(GEN_KEY, JSON.stringify({ topics, brand: $brand.value, seed: $seed.value, saved_at: new Date().toISOString() })); } catch {}
      if ($genMeta) $genMeta.textContent = `Generated at ${new Date().toLocaleString()}`;
      renderList(topics);
      $status.textContent = 'Pick a topic to edit in Notebook.';
    } catch (e) {
      $status.textContent = `Error: ${e.message}`;
    }
  };

  if ($btnClear) {
    $btnClear.onclick = () => {
      try { localStorage.removeItem(GEN_KEY); } catch {}
      $wrap.innerHTML = '';
      if ($genMeta) $genMeta.textContent = '';
      $status.textContent = 'Cleared saved topics.';
    };
  }

  // Restore list initially and on pageshow
  function restore() {
    try {
      const raw = localStorage.getItem(GEN_KEY);
      if (!raw) return;
      const obj = JSON.parse(raw);
      const arr = Array.isArray(obj.topics) ? obj.topics : [];
      if (!arr.length) return;
      if (obj.brand) $brand.value = obj.brand;
      if (obj.seed) $seed.value = obj.seed;
      renderList(arr);
      if ($genMeta && obj.saved_at) $genMeta.textContent = `Generated at ${new Date(obj.saved_at).toLocaleString()}`;
      $status.textContent = 'Restored saved topics.';
    } catch {}
  }
  restore();
  window.addEventListener('pageshow', () => { if (!$wrap.children.length) restore(); });
}

document.addEventListener('DOMContentLoaded', main);
