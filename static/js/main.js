document.addEventListener('DOMContentLoaded', () => {

    // 1. Ocultar alertas automáticas después de 4 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 4000);
    });

    // 2. Confirmación previa a realizar el Pago
    const formPago = document.querySelector('form[action*="pagar"]');
    if (formPago) {
        formPago.addEventListener('submit', (e) => {
            const confirmacion = confirm("¿Desea proceder con el pago? El stock se descontará de forma inmediata.");
            if (!confirmacion) {
                e.preventDefault();
            }
        });
    }

    // 3. Feedback visual al presionar "Agregar al Carro"
    const botonesAgregar = document.querySelectorAll('a[href*="agregar"]');
    botonesAgregar.forEach(btn => {
        btn.addEventListener('click', (e) => {
            btn.classList.add('disabled');
            btn.innerHTML = 'Adding... 🍂';
        });
    });
});