/**
 * Shared utilities for the web UI.
 */

function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name + '=')) {
            return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    return '';
}

async function apiFetch(url, options = {}) {
    const defaults = {
        headers: {
            'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
    };
    if (!(options.body instanceof FormData)) {
        defaults.headers['Content-Type'] = 'application/json';
    }
    const merged = {...defaults, ...options};
    merged.headers = {...defaults.headers, ...(options.headers || {})};

    // Remove Content-Type for FormData so browser sets boundary
    if (options.body instanceof FormData) {
        delete merged.headers['Content-Type'];
    }

    const response = await fetch(url, merged);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

function showNotification(message, type) {
    type = type || 'info';
    const container = document.getElementById('messages');
    if (!container) return;
    const alert = document.createElement('div');
    alert.className = 'alert alert-' + type + ' alert-dismissible fade show';
    alert.innerHTML = message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
    container.appendChild(alert);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
