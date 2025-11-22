document.addEventListener('DOMContentLoaded', function() {
    
    // --- Lógica para eliminar evidencia y mantenimiento ---
    window.eliminarEvidencia = function(id) {
        if (confirm("¿Seguro que deseas eliminar esta evidencia?")) {
            fetch(`/evidencia/eliminar/${id}`, {
                method: "POST"
            }).then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    alert("Hubo un error al eliminar la evidencia.");
                }
            });
        }
    }

    window.eliminarMantenimiento = function(id) {
        if (confirm("¿Estás seguro de que deseas eliminar este mantenimiento?")) {
            // No es necesario usar fetch si ya tienes un formulario, pero si prefieres JS:
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/mantenimiento/eliminar/${id}`;
            document.body.appendChild(form);
            form.submit();
        }
    }
    
    // --- Nueva Lógica para la Integración de IA ---
    const btnGenerarDetalle = document.getElementById('btn-generar-detalle');
    const btnGenerarEstructura = document.getElementById('btn-generar-estructura');
    
    const detalleUsuarioText = document.getElementById('detalle_mantenimiento');
    const detalleSistemaText = document.getElementById('detalle_sistema');

    // Función para actualizar el estado de los botones de IA
    function actualizarEstadoBotonesIA() {
        if (detalleUsuarioText) {
            btnGenerarDetalle.disabled = detalleUsuarioText.value.trim() === '';
        }
        if (detalleSistemaText) {
            btnGenerarEstructura.disabled = detalleSistemaText.value.trim() === '';
        }
    }

    // Añadir listeners para habilitar/deshabilitar botones en tiempo real
    if (detalleUsuarioText) {
        detalleUsuarioText.addEventListener('input', actualizarEstadoBotonesIA);
    }
    if (detalleSistemaText) {
        detalleSistemaText.addEventListener('input', actualizarEstadoBotonesIA);
    }
    
    // Llamada inicial para establecer el estado correcto al cargar la página
    actualizarEstadoBotonesIA();

    // Listener para el botón de generar "Detalle del Sistema"
    if (btnGenerarDetalle) {
        btnGenerarDetalle.addEventListener('click', async function() {
            const spinner = this.querySelector('.spinner-border');
            this.disabled = true;
            spinner.classList.remove('d-none');

            const data = {
                clasificacion: document.getElementById('clase_id').options[document.getElementById('clase_id').selectedIndex].text,
                tipo: document.getElementById('tipo_mantenimiento').value,
                activo: document.getElementById('descripcion_activo').value,
                actividades_usuario: detalleUsuarioText.value,
                locacion: document.getElementById('locacion').value
            };

            try {
                const response = await fetch('/generar/detalle-sistema', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (response.ok) {
                    detalleSistemaText.value = result.detalle;
                    // Disparar el evento 'input' para que se actualice el estado del otro botón
                    detalleSistemaText.dispatchEvent(new Event('input'));
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Ha ocurrido un error de conexión.');
                console.error('Error:', error);
            } finally {
                this.disabled = false;
                spinner.classList.add('d-none');
                actualizarEstadoBotonesIA();
            }
        });
    }

    // Listener para el botón de generar "Información Estructurada"
    if (btnGenerarEstructura) {
        btnGenerarEstructura.addEventListener('click', async function() {
            const spinner = this.querySelector('.spinner-border');
            this.disabled = true;
            spinner.classList.remove('d-none');

            const data = {
                clasificacion: document.getElementById('clase_id').options[document.getElementById('clase_id').selectedIndex].text,
                tipo: document.getElementById('tipo_mantenimiento').value,
                activo: document.getElementById('descripcion_activo').value,
                codigo: document.getElementById('codigo_mantenimiento').value,
                detalle_sistema: detalleSistemaText.value
            };
            
            try {
                const response = await fetch('/generar/info-estructurada', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (response.ok) {
                    document.getElementById('informacion_estructurada').value = result.info;
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Ha ocurrido un error de conexión.');
                console.error('Error:', error);
            } finally {
                this.disabled = false;
                spinner.classList.add('d-none');
            }
        });
    }

    const btnGenerarReporte = document.getElementById('btn-generar-reporte');
    const infoEstructuradaText = document.getElementById('informacion_estructurada');
    const autorInput = document.getElementById('autor');
    const supervisorInput = document.getElementById('supervisor');

    // Función para habilitar/deshabilitar el botón de generar reporte
    function actualizarEstadoBotonReporte() {
        if (btnGenerarReporte) {
            const infoOk = infoEstructuradaText.value.trim() !== '';
            const autorOk = autorInput.value.trim() !== '';
            const supervisorOk = supervisorInput.value.trim() !== '';
            btnGenerarReporte.disabled = !(infoOk && autorOk && supervisorOk);
        }
    }

    // Añadir listeners para los campos relevantes
    if (infoEstructuradaText) infoEstructuradaText.addEventListener('input', actualizarEstadoBotonReporte);
    if (autorInput) autorInput.addEventListener('input', actualizarEstadoBotonReporte);
    if (supervisorInput) supervisorInput.addEventListener('input', actualizarEstadoBotonReporte);

    // Llamada inicial para establecer el estado correcto
    actualizarEstadoBotonReporte();

    // Nueva función global para generar el reporte Word
    window.generarReporteWord = async function(id) {
        const spinner = btnGenerarReporte.querySelector('.spinner-border');
        btnGenerarReporte.disabled = true;
        spinner.classList.remove('d-none');

        try {
            const response = await fetch(`/generar-reporte-word/${id}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (response.ok) {
                alert(result.message);
                location.reload(); // Recarga la página para mostrar el botón de descarga
            } else {
                alert('Error: ' + result.error);
                btnGenerarReporte.disabled = false; // Rehabilita el botón si falla
            }
        } catch (error) {
            alert('Ha ocurrido un error de conexión al generar el reporte.');
            console.error('Error:', error);
            btnGenerarReporte.disabled = false;
        } finally {
            spinner.classList.add('d-none');
        }
    }
});