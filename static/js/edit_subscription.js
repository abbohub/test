// static/js/edit_subscription.js

document.addEventListener('DOMContentLoaded', () => {
  const catSelect = document.getElementById('categorie_id');
  const subcatSelect = document.getElementById('subcategorie_id');

  if (!catSelect || !subcatSelect) return;

  catSelect.addEventListener('change', () => {
    const categorieId = catSelect.value;
    if (!categorieId) {
      subcatSelect.innerHTML = '<option value="">– Kies eerst een categorie –</option>';
      return;
    }

    fetch(`/api/subcategorieen/${categorieId}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Error ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        subcatSelect.innerHTML = ''; // oude opties wissen
        data.forEach(subcategorie => {
          const option = document.createElement('option');
          option.value = subcategorie.id;
          option.textContent = subcategorie.naam;
          subcatSelect.appendChild(option);
        });
      })
      .catch(err => {
        console.error('Kon subcategorieën niet laden:', err);
        subcatSelect.innerHTML = '<option value="">Fout bij laden</option>';
      });
  });

  // Trigger direct bij load als er al een categorie is geselecteerd
  if (catSelect.value) {
    catSelect.dispatchEvent(new Event('change'));
  }
});
// in static/js/edit_subscription.js
document.addEventListener('DOMContentLoaded', () => {
  const catSelect = document.getElementById('categorie_id');
  catSelect?.addEventListener('change', () => {
    laadSubcategorieen(catSelect.value);
  });
  // init bij laden
  if (catSelect?.value) laadSubcategorieen(catSelect.value);
});

