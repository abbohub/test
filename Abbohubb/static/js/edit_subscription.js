// static/js/edit_subscription.js

document.addEventListener("DOMContentLoaded", () => {
  const catSelect = document.getElementById("categorie_id");
  const subcatSelect = document.getElementById("subcategorie_id");

  if (!catSelect || !subcatSelect) return;

  async function laadSubcategorieen(categorieId, selectedId = null) {
    // Reset state
    subcatSelect.innerHTML = '<option value="">Selecteer een subcategorie</option>';

    if (!categorieId) {
      subcatSelect.innerHTML = '<option value="">– Kies eerst een categorie –</option>';
      return;
    }

    try {
      const res = await fetch(`/api/subcategorieen/${encodeURIComponent(categorieId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      data.forEach((subcategorie) => {
        const opt = document.createElement("option");
        opt.value = String(subcategorie.id);
        opt.textContent = subcategorie.naam;

        if (selectedId && String(subcategorie.id) === String(selectedId)) {
          opt.selected = true;
        }

        subcatSelect.appendChild(opt);
      });
    } catch (err) {
      console.error("Kon subcategorieën niet laden:", err);
      subcatSelect.innerHTML = '<option value="">Fout bij laden</option>';
    }
  }

  // On change: reload subcats, probeer huidige selectie te behouden als die nog bestaat
  catSelect.addEventListener("change", () => {
    const currentSelected = subcatSelect.value || subcatSelect.dataset.selected;
    laadSubcategorieen(catSelect.value, currentSelected);
  });

  // Init on load: laad subcats voor gekozen categorie + selecteer huidige subcategorie
  const selectedId = subcatSelect.dataset.selected || subcatSelect.value;
  if (catSelect.value) {
    laadSubcategorieen(catSelect.value, selectedId);
  }
});

  document.addEventListener("DOMContentLoaded", () => {
    const sel = document.getElementById("bedrijf_id");
    const box = document.getElementById("newBedrijfFields");

    function toggle() {
      box.style.display = (sel.value === "__new__") ? "block" : "none";
    }
    sel.addEventListener("change", toggle);
    toggle();
  });