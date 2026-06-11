/* Syndicate Streets – client-side game utilities */

// ── Countdown timers ────────────────────────────────────────────────
function formatDuration(secs) {
  if (secs <= 0) return '00:00';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}h ${mm}m ${ss}s` : `${mm}m ${ss}s`;
}

function tickCountdowns() {
  document.querySelectorAll('.countdown[data-until]').forEach(el => {
    const until = new Date(el.dataset.until + 'Z');
    const secs = Math.max(0, Math.floor((until - Date.now()) / 1000));
    el.textContent = secs > 0 ? formatDuration(secs) : '✅ Free';
    if (secs === 0) {
      // Reload the page when a timer expires so the server re-evaluates
      setTimeout(() => location.reload(), 500);
    }
  });
}

setInterval(tickCountdowns, 1000);
tickCountdowns();

// ── Notification polling ─────────────────────────────────────────────
(function notifPoll() {
  const badge = document.getElementById('notif-badge');
  const count = document.getElementById('notif-count');
  if (!badge) return;

  let lastId = 0;
  let total = 0;

  function poll() {
    fetch('/notifications/poll?since=' + lastId)
      .then(r => r.json())
      .then(msgs => {
        if (!msgs.length) return;
        lastId = msgs[msgs.length - 1].id;
        total += msgs.length;
        count.textContent = total;
        badge.style.display = 'inline';
      })
      .catch(() => {});
  }

  setInterval(poll, 8000);
  poll();
})();

// ── Auto-dismiss flash messages ──────────────────────────────────────
setTimeout(() => {
  const flashes = document.getElementById('flashes');
  if (flashes) {
    flashes.style.transition = 'opacity 0.5s';
    flashes.style.opacity = '0';
    setTimeout(() => flashes.remove(), 500);
  }
}, 5000);

// ── AJAX form submit (crimes, gym) ────────────────────────────────────
// Intercept forms that have data-ajax="true" and POST via fetch,
// then update stat bar values from the JSON response.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-ajax]').forEach(form => {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type=submit]');
      if (btn) btn.disabled = true;
      try {
        const res = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (res.redirected) { location.href = res.url; return; }
        const data = await res.json();
        if (data.flash) showFlash(data.flash.msg, data.flash.cat);
        if (data.redirect) { location.href = data.redirect; return; }
        if (data.reload) { location.reload(); return; }
      } catch(err) {
        location.reload();
      }
    });
  });
});

function showFlash(msg, cat) {
  const div = document.createElement('div');
  div.className = 'flash flash-' + (cat || 'info');
  div.textContent = msg;
  const container = document.getElementById('flashes') || (() => {
    const c = document.createElement('div');
    c.id = 'flashes';
    document.getElementById('content').prepend(c);
    return c;
  })();
  container.prepend(div);
  setTimeout(() => div.remove(), 5000);
}
