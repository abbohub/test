// static/js/main.js
document.addEventListener("DOMContentLoaded", function () {
  // 1. outgoing link analytics
  document.querySelectorAll(".visit-website").forEach(link => {
    link.addEventListener("click", () => {
      const abonnement = link.dataset.abonnement || "onbekend";
      gtag('event', 'klik_naar_aanbieder', {
        'event_category': 'Uitgaande klik',
        'event_label': abonnement,
        'pagina': window.location.pathname
      });
    });
  });

  // 2. sterren-rating interactiviteit
  const scoreInput = document.getElementById('score');
  const stars = document.querySelectorAll('.star');
  function updateStars(value) {
    stars.forEach((star, idx) => {
      const starValue = idx + 1;
      if (value >= starValue) {
        star.classList.add('filled');
        star.classList.remove('half-filled');
      } else if (value >= starValue - 0.5) {
        star.classList.add('half-filled');
        star.classList.remove('filled');
      } else {
        star.classList.remove('filled', 'half-filled');
      }
    });
  }
  document.querySelectorAll('.half').forEach(half => {
    half.addEventListener('mouseenter', () => {
      updateStars(parseFloat(half.dataset.value));
    });
    half.addEventListener('click', () => {
      const val = parseFloat(half.dataset.value);
      scoreInput.value = val;
      updateStars(val);
    });
  });
  document.getElementById('rating-stars')
          .addEventListener('mouseleave', () => updateStars(parseFloat(scoreInput.value) || 0));

  // 3. vergelijkSlugs functie
  window.vergelijkSlugs = function(slug1, slug2) {
    const slugs = [slug1, slug2];
    document.cookie = "comparison_slugs=" + slugs.join(",") + "; path=/; max-age=604800";
    window.location.href = "/vergelijk?abonnementen=" + slugs.join(",");
  };
});

  const collapsible = document.getElementById('collapsible-header');
  let isCollapsed = false;

  window.addEventListener('scroll', () => {
    const shouldCollapse = window.scrollY > 100;

    if (shouldCollapse && !isCollapsed) {
      collapsible.classList.add('collapsed');
      isCollapsed = true;
    } else if (!shouldCollapse && isCollapsed) {
      collapsible.classList.remove('collapsed');
      isCollapsed = false;
    }
  });