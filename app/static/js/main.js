/**
 * =======================================
 * Main JavaScript for the Application
 * =======================================
 */

// =======================================
// --- Authentication & Token Helpers ---
// =======================================

const TOKEN_KEY = 'accessToken';

/**
 * Stores the JWT token in local storage.
 * @param {string} token - The JWT token.
 */
function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Retrieves the JWT token from local storage.
 * @returns {string|null} The JWT token or null if not found.
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Removes the JWT token from local storage.
 */
function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
}

/**
 * Handles the logout process.
 */
function logout() {
    removeToken();
    window.location.href = '/login';
}

// =======================================
// --- API Communication Helpers ---
// =======================================

/**
 * A wrapper for the fetch API to include auth tokens and handle errors.
 * @param {string} url - The URL to fetch.
 * @param {object} options - The options for the fetch request.
 * @returns {Promise<any>} The response from the server.
 */
async function apiCall(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    // Handle 401 Unauthorized - redirect to login
    if (response.status === 401) {
        removeToken();
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'An unknown error occurred.' }));
        throw new Error(errorData.detail || 'API request failed');
    }

    // For 204 No Content, response.json() will fail
    if (response.status === 204) {
        return null;
    }

    return response.json();
}

/**
 * API call specifically for FormData (multipart/form-data).
 * @param {string} url - The URL to fetch.
 * @param {FormData} formData - The FormData object.
 * @returns {Promise<any>} The response from the server.
 */
async function apiCallFormData(url, formData) {
    const token = getToken();
    const headers = {};

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Do NOT set Content-Type for FormData - browser will set it automatically

    const response = await fetch(url, {
        method: 'POST',
        headers,
        body: formData,
    });

    // Handle 401 Unauthorized - redirect to login
    if (response.status === 401) {
        removeToken();
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'An unknown error occurred.' }));
        throw new Error(errorData.detail || 'API request failed');
    }

    // For 204 No Content, response.json() will fail
    if (response.status === 204) {
        return null;
    }

    return response.json();
}

// =======================================
// --- UI Helper Functions ---
// =======================================

/**
 * Shows an alert message.
 * @param {string} message - The message to display.
 * @param {string} type - The alert type (success, danger, warning, info).
 */
function showAlert(message, type = 'info') {
    // Try to find existing alert container
    let alertContainer = document.getElementById('alert-container');

    if (!alertContainer) {
        // Create alert container if it doesn't exist
        alertContainer = document.createElement('div');
        alertContainer.id = 'alert-container';
        alertContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        document.body.appendChild(alertContainer);
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.style.cssText = 'margin-bottom: 10px; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);';
    alert.textContent = message;

    // Set background color based on type
    const colors = {
        success: '#d4edda',
        danger: '#f8d7da',
        warning: '#fff3cd',
        info: '#d1ecf1'
    };
    alert.style.backgroundColor = colors[type] || colors.info;

    alertContainer.appendChild(alert);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.remove();
        // Remove container if empty
        if (alertContainer.children.length === 0) {
            alertContainer.remove();
        }
    }, 5000);
}

/**
 * Shows a loading indicator.
 */
function showLoading() {
    let loadingDiv = document.getElementById('loading-overlay');

    if (!loadingDiv) {
        loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-overlay';
        loadingDiv.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;
        loadingDiv.innerHTML = `
            <div style="background: white; padding: 20px 40px; border-radius: 8px; text-align: center;">
                <div style="border: 4px solid #f3f3f3; border-top: 4px solid #007bff; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                <div>読み込み中...</div>
            </div>
        `;
        document.body.appendChild(loadingDiv);

        // Add animation style
        if (!document.getElementById('loading-animation-style')) {
            const style = document.createElement('style');
            style.id = 'loading-animation-style';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
    }

    loadingDiv.style.display = 'flex';
}

/**
 * Hides the loading indicator.
 */
function hideLoading() {
    const loadingDiv = document.getElementById('loading-overlay');
    if (loadingDiv) {
        loadingDiv.style.display = 'none';
    }
}
