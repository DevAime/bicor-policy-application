// Form validation and enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Auto-format phone numbers
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    });

    // Numeric input validation
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    });

    // Auto-close alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Dynamic sous type loading
function initSousTypeDropdown() {
    const typeBienSelect = document.getElementById('TypeBienID');
    const sousTypeSelect = document.getElementById('SousTypeBienID');

    if (typeBienSelect && sousTypeSelect) {
        typeBienSelect.addEventListener('change', function() {
            const typeBienID = this.value;

            if (typeBienID) {
                fetch(`/api/sous-types/${typeBienID}`)
                    .then(response => response.json())
                    .then(data => {
                        sousTypeSelect.innerHTML = '<option value="">Select Sous Type Bien</option>';
                        data.forEach(sousType => {
                            const option = document.createElement('option');
                            option.value = sousType.SousTypeBienID;
                            option.textContent = sousType.SousTypeBienName;
                            sousTypeSelect.appendChild(option);
                        });
                    })
                    .catch(error => console.error('Error loading sous types:', error));
            } else {
                sousTypeSelect.innerHTML = '<option value="">Select Sous Type Bien</option>';
            }
        });
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    initSousTypeDropdown();
});
