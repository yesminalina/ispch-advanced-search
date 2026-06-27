const funcionSelect = document.getElementById('funcion-empresa');
const razonSocialInput = document.getElementById('razon-social-input');
const paisSelect = document.getElementById('pais-select');
const searchForm = document.getElementById('search-form');
const results = document.getElementById('results');
const clearButton = document.getElementById('clear-form');

// Habilita/deshabilita razón social y país según si se eligió una función
funcionSelect.addEventListener('change', () => {
    const funcionOn = funcionSelect.value !== "";
    razonSocialInput.disabled = !funcionOn;
    paisSelect.disabled = !funcionOn;
});

// Botón Limpiar: vacía el form y re-deshabilita los campos dependientes de función
clearButton.addEventListener('click', () => {
    searchForm.reset();
    razonSocialInput.disabled = true;
    paisSelect.disabled = true;
});

// Scroll suave a resultados al terminar la búsqueda (no aplica a la paginación,
// cuyos controles viven dentro de #results y no disparan este evento en el form)
searchForm.addEventListener('htmx:afterRequest', () => {
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
