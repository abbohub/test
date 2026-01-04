// static/js/index.js
document.addEventListener("DOMContentLoaded", () => {
  // ———————————————
  // 1) Chatbot: verzenden en ontvangen
  // ———————————————
  const sendBtn    = document.getElementById("send-btn");
  const userInput  = document.getElementById("user-message");
  const chatlog    = document.getElementById("chatlog");

  if (sendBtn && userInput && chatlog) {
    sendBtn.addEventListener("click", () => {
      const vraag = userInput.value.trim();
      if (!vraag) return;

      // Eigen bericht
      chatlog.innerHTML += `<div><b>Jij:</b> ${vraag}</div>`;
      userInput.value = "";

      fetch(`/chatbot/?vraag=${encodeURIComponent(vraag)}`)
        .then(res => res.json())
        .then(data => {
          let antwoord = "";
          if (Array.isArray(data.antwoord)) {
            antwoord = data.antwoord
              .map(a => `${a.naam}: ${a.prijs}`)
              .join("<br>");
          } else {
            antwoord = data.antwoord;
          }
          chatlog.innerHTML += `<div><b>Adviseur:</b> ${antwoord}</div>`;
          chatlog.scrollTop = chatlog.scrollHeight;
        })
        .catch(() => {
          chatlog.innerHTML += `<div><b>Bot:</b> Er is een fout opgetreden.</div>`;
        });
    });
  }

  // ———————————————
  // 2) Chatbox toggles (open / sluiten / minimaliseren)
  // ———————————————
  const chatbox      = document.getElementById("chatbox");
  const toggleChat   = document.getElementById("toggle-chat");
  const closeChat    = document.getElementById("close-chat");

  if (chatbox && toggleChat) {
    toggleChat.addEventListener("click", () => {
      const isHidden = chatbox.classList.toggle("hidden");
      chatbox.style.display = isHidden ? "none" : "flex";
    });
  }
  if (chatbox && closeChat) {
    closeChat.addEventListener("click", () => {
      chatbox.classList.add("hidden");
      chatbox.style.display = "none";
    });
  }

 // ———————————————
// 3) Vergelijk-knoppen (meerdere links)
// ———————————————
const vergelijkLinks = document.querySelectorAll(".js-vergelijk-link");
const vergelijkKnop  = document.getElementById("vergelijk-knop"); // alleen nog voor 'hide' op mobiel
const checkboxes     = document.querySelectorAll(".vergelijk-checkbox");

function updateVergelijkLinks() {
  const slugs = Array.from(checkboxes)
    .filter(cb => cb.checked)
    .map(cb => cb.value);

  const href = (slugs.length >= 2)
    ? `/vergelijk?abonnementen=${slugs.join(",")}`
    : "#";

  vergelijkLinks.forEach(link => link.href = href);
}

checkboxes.forEach(cb => cb.addEventListener("change", updateVergelijkLinks));
updateVergelijkLinks(); // init

// Optioneel: voorkom klikken als er <2 geselecteerd zijn
vergelijkLinks.forEach(link => {
  link.addEventListener("click", (e) => {
    const selected = Array.from(checkboxes).filter(cb => cb.checked).length;
    if (selected < 2) {
      e.preventDefault();
      alert("Selecteer minimaal 2 abonnementen om te vergelijken.");
    }
  });
});

// mobiele menu: hide ALLEEN de bovenste vergelijk-knop bij categorie-klik
if (window.matchMedia("(max-width: 768px)").matches) {
  document.querySelectorAll(".dropdown-menu a").forEach(link => {
    link.addEventListener("click", () => {
      if (vergelijkKnop) vergelijkKnop.style.display = "none";
    });
  });
}

  // ———————————————
  // 4) Endless carousel per categorie
  // ———————————————
  document.querySelectorAll(".categorie-scroll-wrapper").forEach(wrapper => {
    const container  = wrapper.querySelector(".categorie-scroll-container");
    const list       = container?.querySelector(".abonnementen-lijst");
    const leftArrow  = wrapper.querySelector(".scroll-arrow-left");
    const rightArrow = wrapper.querySelector(".scroll-arrow-right");
    if (!container || !list || !leftArrow || !rightArrow) return;

    const isMobile  = window.matchMedia("(max-width: 768px)").matches;
    const tileCount = list.children.length;
    if ((!isMobile && tileCount < 4) || (isMobile && tileCount < 2)) return;

    // klonen
    if (!container.dataset.duplicated) {
      container.appendChild(list.cloneNode(true));
      container.appendChild(list.cloneNode(true));
      container.dataset.duplicated = "true";
    }
    leftArrow.style.display = "none";

    const gap       = 20;
    const tile      = list.querySelector(".abonnement");
    const step      = (tile?.offsetWidth || 300) + gap;
    const wrapAt    = list.offsetWidth * 2;

    container.addEventListener("scroll", () => {
      const pos = container.scrollLeft;
      if (pos >= wrapAt)        container.scrollLeft = pos - wrapAt;
      else if (pos < 0)         container.scrollLeft = pos + wrapAt;
      leftArrow.style.display = (container.scrollLeft > 0) ? "flex" : "none";
    });
    rightArrow.addEventListener("click", () => container.scrollBy({ left: step, behavior: "smooth" }));
    leftArrow.addEventListener("click",  () => container.scrollBy({ left: -step, behavior: "smooth" }));
  });
});

//<!-- Sidebar-script -->
function toggleSidebar() {
  const sidebar = document.getElementById("categorieSidebar");
  if (!sidebar) return;
  sidebar.style.right = sidebar.style.right === "0px" ? "-380px" : "0px";
}

function toggleSidebar() {
  // Desktop toggle
  const sidebar = document.getElementById("categorieSidebar");
  if (window.innerWidth > 768) {
    if (!sidebar) return;
    sidebar.style.right = sidebar.style.right === "0px" ? "-360px" : "0px";
  } else {
    // Mobiel: open overlay
    toggleMobileOverlay();
  }
}

function toggleMobileOverlay() {
  const overlay = document.getElementById("categorieOverlayMobile");
  overlay.classList.toggle("show");
}

// querie builder
(function () {
  const cat = document.getElementById("categorie");
  const sub = document.getElementById("subcategorie");
  if (!cat || !sub) return;

  function filterSubcats() {
    const selectedCat = cat.value;
    const opts = Array.from(sub.options);

    // altijd de "Alle subcategorieën" zichtbaar laten
    opts.forEach(o => {
      if (!o.value) {
        o.hidden = false;
        return;
      }
      const oCat = o.getAttribute("data-cat");
      o.hidden = !!selectedCat && oCat !== selectedCat;
    });

    // als huidige subcategorie niet meer past -> reset
    const selectedOpt = sub.options[sub.selectedIndex];
    if (selectedOpt && selectedOpt.hidden) {
      sub.value = "";
    }
  }

  cat.addEventListener("change", filterSubcats);
  // run bij laden (zodat bij refresh alles netjes staat)
  filterSubcats();
})();
(function () {
  const cat = document.getElementById("f-categorie");
  const sub = document.getElementById("f-subcategorie");
  const btnApply = document.getElementById("btn-apply-filters");
  const btnReset = document.getElementById("btn-reset");

  // Drawer (mobile)
  const drawer = document.getElementById("filters-drawer");
  const backdrop = document.getElementById("filters-backdrop");
  const btnOpen = document.getElementById("btn-open-filters");
  const btnClose = document.getElementById("btn-close-filters");

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add("open");
    document.body.classList.add("filters-open");
    backdrop?.classList.add("show");
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    document.body.classList.remove("filters-open");
    backdrop?.classList.remove("show");
  }

  btnOpen?.addEventListener("click", openDrawer);
  btnClose?.addEventListener("click", closeDrawer);
  backdrop?.addEventListener("click", closeDrawer);

  // --- Subcategorie opties filteren op categorie ---
  function filterSubcats() {
    if (!sub) return;
    const selectedCatId = cat?.value || "";

    let hasSelectedOption = false;

    [...sub.options].forEach((opt) => {
      if (!opt.value) {
        opt.hidden = false;
        return;
      }
      const optCat = opt.dataset.categorie || "";
      const show = !selectedCatId || optCat === selectedCatId;
      opt.hidden = !show;

      if (show && opt.selected) hasSelectedOption = true;
    });

    // Als huidige subcategorie niet bij categorie hoort → reset naar leeg
    if (selectedCatId && !hasSelectedOption) {
      sub.value = "";
    }
  }

  cat?.addEventListener("change", filterSubcats);
  filterSubcats(); // init bij page load

  // --- Apply: bouw querystring voor jouw builder keys ---
  function applyFilters() {
    const params = new URLSearchParams(window.location.search);

    // q (zoekterm in sidebar)
    const qEl = document.getElementById("f-q");
    const qVal = (qEl?.value || "").trim();
    if (qVal) params.set("q", qVal);
    else params.delete("q");

    // categorie/subcategorie (IDs)
    if (cat?.value) params.set("categorie_id", cat.value);
    else params.delete("categorie_id");

    if (sub?.value) params.set("subcategorie_id", sub.value);
    else params.delete("subcategorie_id");

    // sort/billing/price/pause
    const sort = document.getElementById("f-sort")?.value || "";
    if (sort) params.set("sort", sort); else params.delete("sort");

    const billing = document.getElementById("f-billing")?.value || "";
    if (billing) params.set("billing_period", billing); else params.delete("billing_period");

    const pmin = document.getElementById("f-price-min")?.value || "";
    const pmax = document.getElementById("f-price-max")?.value || "";
    if (pmin) params.set("price_min", pmin); else params.delete("price_min");
    if (pmax) params.set("price_max", pmax); else params.delete("price_max");

    const pause = document.getElementById("f-pause")?.value || "";
    if (pause !== "") params.set("pause_possible", pause);
    else params.delete("pause_possible");

    // countries multiselect
    const countries = document.getElementById("f-countries");
    params.delete("countries");
    if (countries) {
      [...countries.selectedOptions].forEach((opt) => params.append("countries", opt.value));
    }

    // paginering resetten bij filter-change
    params.delete("page");

    window.location.href = `${window.location.pathname}?${params.toString()}`;
  }

  btnApply?.addEventListener("click", () => {
    applyFilters();
    closeDrawer();
  });

  // Reset: alles weg, terug naar /
  btnReset?.addEventListener("click", () => {
    window.location.href = window.location.pathname;
  });
})();

document.addEventListener("DOMContentLoaded", () => {
  const source = document.getElementById("cat-desc-source");
  if (!source) return;

  const html = source.innerHTML;
  const m = document.getElementById("cat-desc-mobile");
  const d = document.getElementById("cat-desc-desktop");
  if (m) m.innerHTML = html;
  if (d) d.innerHTML = html;
});

