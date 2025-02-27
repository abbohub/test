document.querySelectorAll('.category-row').forEach(row => {
    const leftButton = document.createElement('button');
    const rightButton = document.createElement('button');

    leftButton.innerText = '<';
    rightButton.innerText = '>';

    leftButton.classList.add('scroll-btn', 'left');
    rightButton.classList.add('scroll-btn', 'right');

    row.parentElement.append(leftButton, rightButton);

    leftButton.addEventListener('click', () => {
        row.scrollBy({ left: -300, behavior: 'smooth' });
    });

    rightButton.addEventListener('click', () => {
        row.scrollBy({ left: 300, behavior: 'smooth' });
    });
});
document.getElementById('categorie-dropdown').addEventListener('change', function () {
    const selected = this.value;
    const categorieSecties = document.querySelectorAll('.categorie');

    categorieSecties.forEach(sectie => {
        if (selected === '' || sectie.dataset.categorieId === selected) {
            sectie.style.display = ''; // Toon de geselecteerde categorie
        } else {
            sectie.style.display = 'none'; // Verberg andere categorieën
        }
    });
});
