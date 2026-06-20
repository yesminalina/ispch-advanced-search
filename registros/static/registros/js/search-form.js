const funcionSelect = document.getElementById('funcion-empresa');
const razonSocialInput = document.getElementById('razon-social-input');
const paisSelect = document.getElementById('pais-select');

funcionSelect.addEventListener('change', () => {
    const funcionOn = funcionSelect.value !== "";
    razonSocialInput.disabled = !funcionOn;
    paisSelect.disabled = !funcionOn;
});