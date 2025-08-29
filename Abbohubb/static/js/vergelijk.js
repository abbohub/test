// static/js/vergelijk.js
document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------
  // 1) "Vergelijking wissen" knop (bestaande functionaliteit)
  // -------------------------------------------------
  const btnClear = document.getElementById('clear-comparison');
  if (btnClear) {
    btnClear.addEventListener('click', () => {
      const csrfToken =
        document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

      fetch('/clear_comparison', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        credentials: 'same-origin' // stuur cookie/session mee
      })
        .then((resp) => {
          if (resp.ok) {
            window.location.href = '/';
          } else {
            console.error('Vergelijking wissen mislukt:', resp.statusText);
          }
        })
        .catch((err) => console.error('Fout bij clear_comparison:', err));
    });
  }

  // -------------------------------------------------
  // 2) Outgoing link analytics voor "Bezoek aanbieder"
  //    - event delegation (werkt ook voor dynamisch toegevoegde knoppen)
  //    - GA4 guard zodat gtag afwezigheid/AD-block geen errors geeft
  // -------------------------------------------------
  document.addEventListener('click', (e) => {
    const link = e.target.closest('.visit-website');
    if (!link) return;

    const abonnement = link.dataset.abonnement || 'onbekend';
    const href = link.getAttribute('href') || '';
    const path = window.location.pathname;

    try {
      if (typeof gtag === 'function') {
        gtag('event', 'klik_naar_aanbieder', {
          event_category: 'Uitgaande klik',
          event_label: abonnement,
          destination: href,
          pagina: path
        });
      }
    } catch (err) {
      // Nooit de klik blokkeren vanwege analytics
      console.warn('GA4 event mislukt:', err);
    }
  });

  // -------------------------------------------------
  // 3) (Optioneel) "Vergelijk cookie" netjes zetten via helper
  //    – Handig als je elders slugs bijwerkt en hier wilt gebruiken
  // -------------------------------------------------
  window.setComparisonSlugs = function (slugsArray) {
    const slugs = (slugsArray || []).filter(Boolean);
    const isHttps = location.protocol === 'https:';
    const attrs = [
      'path=/',
      'max-age=604800',  // 7 dagen
      'SameSite=Lax',
      isHttps ? 'Secure' : ''
    ].filter(Boolean).join('; ');
    document.cookie = 'comparison_slugs=' + encodeURIComponent(slugs.join(',')) + '; ' + attrs;
  };
});
