// Music Search Bot Web - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Validação do formulário
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            const fileInput = document.getElementById('file');
            const delayInput = document.getElementById('delay');
            const retriesInput = document.getElementById('max_retries');
            const concurrencyInput = document.getElementById('concurrency');
            
            // Validação do arquivo
            if (!fileInput.files.length) {
                e.preventDefault();
                showAlert('Por favor, selecione um arquivo CSV.', 'danger');
                return;
            }
            
            const file = fileInput.files[0];
            if (!file.name.toLowerCase().endsWith('.csv')) {
                e.preventDefault();
                showAlert('Por favor, selecione apenas arquivos CSV.', 'danger');
                return;
            }
            
            // Validação dos parâmetros
            const delay = parseFloat(delayInput.value);
            const retries = parseInt(retriesInput.value);
            const concurrency = parseInt(concurrencyInput.value);
            
            if (delay < 0.1 || delay > 10) {
                e.preventDefault();
                showAlert('Delay deve estar entre 0.1 e 10 segundos.', 'danger');
                return;
            }
            
            if (retries < 1 || retries > 10) {
                e.preventDefault();
                showAlert('Max retries deve estar entre 1 e 10.', 'danger');
                return;
            }
            
            if (concurrency < 1 || concurrency > 3) {
                e.preventDefault();
                showAlert('Concorrência deve estar entre 1 e 3.', 'danger');
                return;
            }
            
            // Mostra loading
            showLoading();
        });
    }
    
    // Drag and drop para upload
    const fileInput = document.getElementById('file');
    if (fileInput) {
        const dropZone = fileInput.parentElement;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight(e) {
            dropZone.classList.add('border-primary', 'bg-light');
        }
        
        function unhighlight(e) {
            dropZone.classList.remove('border-primary', 'bg-light');
        }
        
        dropZone.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                fileInput.files = files;
                updateFileLabel(files[0].name);
            }
        }
        
        // Atualiza label quando arquivo é selecionado
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                updateFileLabel(this.files[0].name);
            }
        });
        
        function updateFileLabel(fileName) {
            const label = document.querySelector('label[for="file"]');
            if (label) {
                label.innerHTML = `<i class="fas fa-file-csv"></i> ${fileName}`;
            }
        }
    }
});

function showAlert(message, type = 'info') {
    // Remove alertas existentes
    const existingAlerts = document.querySelectorAll('.alert-custom');
    existingAlerts.forEach(alert => alert.remove());
    
    // Cria novo alerta
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show alert-custom`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insere no topo da página
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Remove automaticamente após 5 segundos
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function showLoading() {
    const submitBtn = document.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
    }
}

// Utilitários para formatação
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatPercentage(value, total) {
    if (total === 0) return '0%';
    return `${Math.round((value / total) * 100)}%`;
}

// Animações suaves
function animateValue(element, start, end, duration) {
    const startTimestamp = performance.now();
    
    function step(timestamp) {
        const elapsed = timestamp - startTimestamp;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.floor(progress * (end - start) + start);
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }
    
    requestAnimationFrame(step);
}

// Função para copiar texto para clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showAlert('Texto copiado para a área de transferência!', 'success');
    }).catch(function(err) {
        console.error('Erro ao copiar texto: ', err);
        showAlert('Erro ao copiar texto.', 'danger');
    });
}

// Função para download com feedback
function downloadWithFeedback(url, filename) {
    showAlert('Iniciando download...', 'info');
    
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    setTimeout(() => {
        showAlert('Download concluído!', 'success');
    }, 1000);
}

// Validação em tempo real dos inputs
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input[type="number"]');
    
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            validateInput(this);
        });
    });
});

function validateInput(input) {
    const value = parseFloat(input.value);
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);
    
    if (value < min || value > max) {
        input.classList.add('is-invalid');
    } else {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
    }
}

