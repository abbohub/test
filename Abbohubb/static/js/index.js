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

