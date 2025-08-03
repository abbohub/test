// static/js/vergelijk.js
document.addEventListener('DOMContentLoaded', () => {
  const btnClear = document.getElementById('clear-comparison');
  if (!btnClear) return; // voorkomt errors als de knop er niet is

  btnClear.addEventListener('click', () => {
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute('content') || '';

    fetch('/clear_comparison', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'same-origin'    // stuur cookie/session met request
    })
    .then(resp => {
      if (resp.ok) {
        window.location.href = '/';
      } else {
        console.error('Vergelijking wissen mislukt:', resp.statusText);
      }
    })
    .catch(err => console.error('Fout bij clear_comparison:', err));
  });
});
