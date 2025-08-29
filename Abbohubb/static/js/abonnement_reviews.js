// static/js/abonnement_reviews.js
document.addEventListener("DOMContentLoaded", function () {
  // ---------- 1) Outgoing link analytics (delegation + GA4 guard) ----------
  document.addEventListener("click", (e) => {
    const link = e.target.closest(".visit-website");
    if (!link) return;

    // Haal wat context op voor rapportage
    const abonnement = link.dataset.abonnement || "onbekend";
    const href = link.getAttribute("href") || "";
    const path = window.location.pathname;

    // GA4 veilig aanroepen (geen crash als gtag niet bestaat)
    try {
      if (typeof gtag === "function") {
        gtag("event", "klik_naar_aanbieder", {
          event_category: "Uitgaande klik",
          event_label: abonnement,
          destination: href,
          pagina: path
        });
      }
    } catch (err) {
      // Stil falen: we willen nooit een blokkade op de klik
      console.warn("GA4 event mislukt:", err);
    }
  });

  // ---------- 2) Sterren-rating interactiviteit (met guards) ----------
  const scoreInput = document.getElementById("score");
  const stars = document.querySelectorAll(".star");
  const ratingWrap = document.getElementById("rating-stars");

  function updateStars(value) {
    stars.forEach((star, idx) => {
      const starValue = idx + 1;
      if (value >= starValue) {
        star.classList.add("filled");
        star.classList.remove("half-filled");
      } else if (value >= starValue - 0.5) {
        star.classList.add("half-filled");
        star.classList.remove("filled");
      } else {
        star.classList.remove("filled", "half-filled");
      }
    });
  }

  if (scoreInput && ratingWrap && stars.length) {
    // Hover/klik op halve sterren
    document.querySelectorAll(".half").forEach((half) => {
      half.addEventListener("mouseenter", () => {
        const v = parseFloat(half.dataset.value);
        if (!isNaN(v)) updateStars(v);
      });
      half.addEventListener("click", () => {
        const v = parseFloat(half.dataset.value);
        if (!isNaN(v)) {
          scoreInput.value = v;
          updateStars(v);
        }
      });
    });

    // Reset hover state wanneer je buiten de sterren gaat
    ratingWrap.addEventListener("mouseleave", () =>
      updateStars(parseFloat(scoreInput.value) || 0)
    );

    // Init state (bij bewerken of herladen)
    updateStars(parseFloat(scoreInput.value) || 0);
  }

  // ---------- 3) VergelijkSlugs helper ----------
  window.vergelijkSlugs = function (slug1, slug2) {
    const slugs = [slug1, slug2].filter(Boolean);
    if (!slugs.length) return;

    // Cookie 7 dagen, met nette flags
    const isHttps = location.protocol === "https:";
    const attrs = [
      "path=/",
      "max-age=604800",
      "SameSite=Lax",
      isHttps ? "Secure" : ""
    ]
      .filter(Boolean)
      .join("; ");

    document.cookie = "comparison_slugs=" + encodeURIComponent(slugs.join(",")) + "; " + attrs;

    // Redirect naar vergelijkpagina
    window.location.href = "/vergelijk?abonnementen=" + slugs.join(",");
  };

  // ---------- 4) Collapsible header (met guard) ----------
  const collapsible = document.getElementById("collapsible-header");
  if (collapsible) {
    let isCollapsed = false;
    window.addEventListener(
      "scroll",
      () => {
        const shouldCollapse = window.scrollY > 100;
        if (shouldCollapse && !isCollapsed) {
          collapsible.classList.add("collapsed");
          isCollapsed = true;
        } else if (!shouldCollapse && isCollapsed) {
          collapsible.classList.remove("collapsed");
          isCollapsed = false;
        }
      },
      { passive: true }
    );
  }
});
