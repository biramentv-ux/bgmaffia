// Concrete Empire — minimal vanilla JS.
// All authority is server-side; this is cosmetic countdowns + polling only.

// ---- countdown timers (data-until = seconds remaining at render) ----
function tickCountdowns() {
  document.querySelectorAll('[data-until]').forEach(el => {
    let secs = parseInt(el.getAttribute('data-until'), 10);
    if (isNaN(secs)) return;
    secs -= 1;
    if (secs <= 0) {
      el.setAttribute('data-until', '0');
      const i = el.querySelector('i');
      if (i) i.textContent = 'ready';
      // reload so the server re-evaluates the lock/cooldown
      if (!el.dataset.reloaded) { el.dataset.reloaded = '1'; setTimeout(() => location.reload(), 600); }
      return;
    }
    el.setAttribute('data-until', secs);
    const i = el.querySelector('i');
    if (i) {
      const m = Math.floor(secs / 60), s = secs % 60;
      i.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
    }
    // crime button cooldown labels
    if (el.dataset.cd) {
      const m = Math.floor(secs / 60), s = secs % 60;
      el.textContent = m > 0 ? `${m}:${String(s).padStart(2, '0')}` : `${s}s`;
    }
  });
}
setInterval(tickCountdowns, 1000);

// ---- toast helper ----
function toast(msg) {
  const box = document.getElementById('toasts');
  if (!box) return;
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

// ---- notification polling (every 8s) ----
async function pollNotifications() {
  try {
    const r = await fetch('/notifications/poll', { headers: { 'X-Requested-With': 'fetch' } });
    if (!r.ok) return;
    const items = await r.json();
    items.forEach(n => toast(n.body));
  } catch (e) { /* offline; ignore */ }
}
setInterval(pollNotifications, 8000);

// ---- AJAX crime submit (progressive enhancement) ----
function updateBars(data) {
  const map = { energy: data.energy, nerve: data.nerve, health: data.health };
  for (const [k, v] of Object.entries(map)) {
    if (v == null) continue;
    const b = document.querySelector(`[data-bar="${k}"]`);
    if (b) b.textContent = v;
    const fill = document.querySelector(`[data-fill="${k}"]`);
    if (fill) {
      const max = parseInt(fill.closest('.bar-block').querySelector('.bar-label span:last-child').textContent.split('/')[1], 10);
      if (max) fill.style.width = Math.min(100, (v / max) * 100) + '%';
    }
  }
  if (data.cash != null) {
    const c = document.querySelector('[data-bar="cash"]');
    if (c) c.textContent = '$' + Number(data.cash).toLocaleString();
  }
}

document.addEventListener('submit', async (e) => {
  const form = e.target;
  if (!form.classList.contains('ajax-crime')) return;
  e.preventDefault();
  const btn = form.querySelector('button');
  if (btn) btn.disabled = true;
  try {
    const r = await fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'fetch' },
      body: new FormData(form)
    });
    const data = await r.json();
    toast(data.msg);
    updateBars(data);
    // refresh cooldown display after a short beat
    setTimeout(() => location.reload(), 1200);
  } catch (err) {
    if (btn) btn.disabled = false;
    location.reload();
  }
});

// ---- chat ----
(function () {
  const log = document.getElementById('chat-log');
  if (!log) return;
  let lastId = 0;
  async function load() {
    try {
      const r = await fetch('/chat/messages?since=' + lastId);
      const msgs = await r.json();
      msgs.forEach(m => {
        lastId = Math.max(lastId, m.id);
        const div = document.createElement('div');
        div.className = 'chat-msg';
        div.innerHTML = `<span class="who"></span><span class="body"></span><span class="when"></span>`;
        div.querySelector('.who').textContent = m.user;
        div.querySelector('.body').textContent = m.body;
        div.querySelector('.when').textContent = m.ts.split(' ')[1] || '';
        log.appendChild(div);
      });
      if (msgs.length) log.scrollTop = log.scrollHeight;
    } catch (e) { /* ignore */ }
  }
  load();
  setInterval(load, 3000);

  const form = document.getElementById('chat-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = form.querySelector('input[name="body"]');
      if (!input.value.trim()) return;
      const fd = new FormData(form);
      await fetch('/chat/send', { method: 'POST', headers: { 'X-Requested-With': 'fetch' }, body: fd });
      input.value = '';
      load();
    });
  }
})();
