/**
 * =======================================
 * Main JavaScript for the Application
 * =======================================
 */

document.addEventListener('DOMContentLoaded', () => {
    const pagePath = window.location.pathname;

    // --- Global Initializations ---
    handleAuthStatus();

    // --- Page-specific Initializations ---
    if (pagePath.endsWith('/login') || pagePath === '/') {
        initLoginPage();
    } else if (pagePath.endsWith('/main')) {
        initMainPage();
    } else if (pagePath.endsWith('/settings')) {
        initSettingsPage();
    } else if (pagePath.endsWith('/admin/users')) {
        initAdminUsersPage();
    }
});

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
 * Checks authentication status and updates UI.
 */
function handleAuthStatus() {
    const token = getToken();
    const nav = document.querySelector('nav');
    if (!nav) return;

    if (token) {
        nav.innerHTML = `
            <a href="/main">Home</a>
            <a href="/settings">Settings</a>
            <button id="logout-button">Logout</button>
        `;
        document.getElementById('logout-button').addEventListener('click', handleLogout);
    } else {
        nav.innerHTML = '<a href="/login">Login</a>';
    }
}

/**
 * Handles the logout process.
 */
function handleLogout() {
    removeToken();
    window.location.href = '/login';
}

// =======================================
// --- API Communication Helper ---
// =======================================

/**
 * A wrapper for the fetch API to include auth tokens and handle errors.
 * @param {string} url - The URL to fetch.
 * @param {object} options - The options for the fetch request.
 * @returns {Promise<any>} The response from the server.
 */
async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = {
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Do not set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

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
// --- Page Initializers ---
// =======================================

/**
 * Initializes the login page.
 */
function initLoginPage() {
    const loginForm = document.getElementById('login-form');
    const errorMessageDiv = document.getElementById('error-message');

    if (!loginForm) return;

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.classList.add('hidden');
        errorMessageDiv.textContent = '';

        const formData = new FormData(loginForm);
        const body = new URLSearchParams();
        body.append('username', formData.get('email'));
        body.append('password', formData.get('password'));

        try {
            const response = await fetch('/api/v1/auth/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: body,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Login failed');
            }

            const data = await response.json();
            saveToken(data.access_token);
            window.location.href = '/main';

        } catch (error) {
            errorMessageDiv.textContent = error.message;
            errorMessageDiv.classList.remove('hidden');
        }
    });
}

/**
 * Initializes the main task page.
 */
async function initMainPage() {
    // --- UI Element References ---
    const taskCreationForm = document.getElementById('task-creation-form');
    const processingView = document.getElementById('processing-view');
    const finishedView = document.getElementById('finished-view');
    const settingsSelect = document.getElementById('setting-id');
    const errorMessageDiv = document.getElementById('error-message');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const finishedMessage = document.getElementById('finished-message');
    const errorReportLink = document.getElementById('error-report-link');
    const cancelTaskButton = document.getElementById('cancel-task-button');
    const finishedOkButton = document.getElementById('finished-ok-button');

    // --- State Variables ---
    let currentState = 'idle'; // idle, processing, finished
    let pollingInterval = null;

    // --- Polling Management ---
    function startPolling() {
        stopPolling(); // Ensure no multiple intervals are running
        pollingInterval = setInterval(async () => {
            try {
                const result = await apiFetch('/api/v1/tasks/status');
                updateProgress(result);
                if (result.status === 'SUCCESS' || result.status === 'FAILURE') {
                    stopPolling();
                    updateUIForState('finished', result);
                }
            } catch (error) {
                stopPolling();
                errorMessageDiv.textContent = `Polling failed: ${error.message}`;
                errorMessageDiv.classList.remove('hidden');
            }
        }, 3000);
    }

    function stopPolling() {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }

    // --- UI State Management ---
    function updateProgress(data) {
        if (!data) return;
        const percent = data.progress || 0;
        progressBar.style.width = `${percent}%`;
        progressBar.textContent = `${Math.round(percent)}%`;
        progressText.textContent = `Processing: ${data.completed_items} / ${data.total_items}`;
    }

    function updateUIForState(state, data = {}) {
        currentState = state;
        errorMessageDiv.classList.add('hidden');
        stopPolling();

        taskCreationForm.classList.add('hidden');
        processingView.classList.add('hidden');
        finishedView.classList.add('hidden');

        if (state === 'idle') {
            taskCreationForm.classList.remove('hidden');
            taskCreationForm.reset();
            populateSettings();
        } else if (state === 'processing') {
            processingView.classList.remove('hidden');
            cancelTaskButton.disabled = false;
            updateProgress(data);
            startPolling();
        } else if (state === 'finished') {
            finishedView.classList.remove('hidden');
            if (data.status === 'SUCCESS') {
                finishedMessage.textContent = 'Task completed successfully!';
                finishedMessage.className = 'alert alert-success';
            } else {
                finishedMessage.textContent = 'Task finished with errors or was cancelled.';
                finishedMessage.className = 'alert alert-warning';
            }
            if (data.has_errors) {
                errorReportLink.classList.remove('hidden');
                // The href should ideally point to a blob URL or a direct download, 
                // but for simplicity, we link to the API endpoint.
                errorReportLink.href = '/api/v1/tasks/error-report';
            } else {
                errorReportLink.classList.add('hidden');
            }
        }
    }

    // --- Data Fetching ---
    async function populateSettings() {
        try {
            const data = await apiFetch('/api/v1/sb-settings');
            settingsSelect.innerHTML = '';
            if (data.settings.length === 0) {
                settingsSelect.innerHTML = '<option disabled selected>No settings found. Please add one.</option>';
                return;
            }
            data.settings.forEach(setting => {
                const option = document.createElement('option');
                option.value = setting.id;
                option.textContent = setting.setting_name;
                settingsSelect.appendChild(option);
            });
        } catch (error) {
            errorMessageDiv.textContent = `Failed to load settings: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    // --- Event Listeners ---
    taskCreationForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorMessageDiv.classList.add('hidden');
        const formData = new FormData(taskCreationForm);
        const imageFiles = document.getElementById('image-files').files;
        for (let i = 0; i < imageFiles.length; i++) {
            formData.append('image_files', imageFiles[i]);
        }
        try {
            await apiFetch('/api/v1/tasks/style-post', {
                method: 'POST',
                body: formData,
            });
            const initialStatus = await apiFetch('/api/v1/tasks/status');
            updateUIForState('processing', initialStatus);
        } catch (error) {
            errorMessageDiv.textContent = `Task creation failed: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    });

    cancelTaskButton.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to cancel the running task?')) return;
        try {
            await apiFetch('/api/v1/tasks/cancel', { method: 'POST' });
            cancelTaskButton.disabled = true;
            cancelTaskButton.textContent = 'Cancelling...';
        } catch (error) {
            errorMessageDiv.textContent = `Failed to cancel task: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    });

    finishedOkButton.addEventListener('click', async () => {
        try {
            await apiFetch('/api/v1/tasks/finished-task', { method: 'DELETE' });
            updateUIForState('idle');
        } catch (error) {
            // If the task is already deleted, just reset the UI
            if (error.message.includes('No finished task to delete')) {
                updateUIForState('idle');
            } else {
                errorMessageDiv.textContent = `Failed to clear finished task: ${error.message}`;
                errorMessageDiv.classList.remove('hidden');
            }
        }
    });

    // --- Initial Page Load Logic ---
    try {
        const status = await apiFetch('/api/v1/tasks/status');
        if (status.status === 'PROCESSING' || status.status === 'CANCELLING') {
            updateUIForState('processing', status);
        } else {
            updateUIForState('finished', status);
        }
    } catch (error) {
        if (error.message.includes('No active task found')) {
            updateUIForState('idle');
        } else {
            errorMessageDiv.textContent = `Error fetching task status: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }
}

/**
 * Initializes the settings page.
 */
async function initSettingsPage() {
    const settingsTableBody = document.getElementById('settings-table-body');
    const addSettingForm = document.getElementById('add-setting-form');
    const errorMessageDiv = document.getElementById('error-message');
    const settingIdField = document.getElementById('setting-id-field');
    const formTitle = document.getElementById('form-title');

    async function loadAndRenderSettings() {
        try {
            const data = await apiFetch('/api/v1/sb-settings');
            settingsTableBody.innerHTML = ''; // Clear table
            data.settings.forEach(setting => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${setting.setting_name}</td>
                    <td>${setting.sb_user_id}</td>
                    <td>${setting.salon_name || 'N/A'}</td>
                    <td>
                        <button class="btn-edit" data-id="${setting.id}">Edit</button>
                        <button class="btn-delete" data-id="${setting.id}">Delete</button>
                    </td>
                `;
                settingsTableBody.appendChild(row);
            });

            // Add event listeners to new buttons
            document.querySelectorAll('.btn-delete').forEach(button => {
                button.addEventListener('click', handleDelete);
            });
            document.querySelectorAll('.btn-edit').forEach(button => {
                button.addEventListener('click', handleEditSetup);
            });

        } catch (error) {
            errorMessageDiv.textContent = `Error loading settings: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    async function handleFormSubmit(event) {
        event.preventDefault();
        errorMessageDiv.classList.add('hidden');
        const formData = new FormData(addSettingForm);
        const settingId = settingIdField.value;

        const body = {
            setting_name: formData.get('setting_name'),
            sb_user_id: formData.get('sb_user_id'),
            salon_id: formData.get('salon_id'),
            salon_name: formData.get('salon_name'),
        };
        // Only include password if it's being set/changed
        if (formData.get('sb_password')) {
            body.sb_password = formData.get('sb_password');
        }

        const method = settingId ? 'PUT' : 'POST';
        const url = settingId ? `/api/v1/sb-settings/${settingId}` : '/api/v1/sb-settings';

        try {
            await apiFetch(url, {
                method: method,
                body: JSON.stringify(body),
            });
            addSettingForm.reset();
            settingIdField.value = '';
            formTitle.textContent = 'Add New Setting';
            await loadAndRenderSettings();
        } catch (error) {
            errorMessageDiv.textContent = `Failed to save setting: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    async function handleDelete(event) {
        const settingId = event.target.dataset.id;
        if (confirm(`Are you sure you want to delete setting #${settingId}?`)) {
            try {
                await apiFetch(`/api/v1/sb-settings/${settingId}`, { method: 'DELETE' });
                await loadAndRenderSettings();
            } catch (error) {
                errorMessageDiv.textContent = `Failed to delete setting: ${error.message}`;
                errorMessageDiv.classList.remove('hidden');
            }
        }
    }

    async function handleEditSetup(event) {
        const settingId = event.target.dataset.id;
        try {
            // Fetch the full setting details to populate the form
            // Note: This requires an endpoint to get a single setting, which we assume exists.
            // If not, we can get it from the already loaded list.
            const settingsData = await apiFetch('/api/v1/sb-settings');
            const setting = settingsData.settings.find(s => s.id == settingId);

            if (setting) {
                formTitle.textContent = `Edit Setting: ${setting.setting_name}`;
                settingIdField.value = setting.id;
                addSettingForm.querySelector('[name="setting_name"]').value = setting.setting_name;
                addSettingForm.querySelector('[name="sb_user_id"]').value = setting.sb_user_id;
                addSettingForm.querySelector('[name="salon_id"]').value = setting.salon_id || '';
                addSettingForm.querySelector('[name="salon_name"]').value = setting.salon_name || '';
                addSettingForm.querySelector('[name="sb_password"]').placeholder = 'Leave blank to keep unchanged';
                window.scrollTo(0, 0); // Scroll to top to see the form
            }
        } catch (error) {
            errorMessageDiv.textContent = `Failed to load setting for editing: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    addSettingForm.addEventListener('submit', handleFormSubmit);
    
    // Initial load
    await loadAndRenderSettings();
}

/**
 * Initializes the admin users page.
 */
async function initAdminUsersPage() {
    const usersTableBody = document.getElementById('users-table-body');
    const addUserForm = document.getElementById('add-user-form');
    const errorMessageDiv = document.getElementById('error-message');

    async function loadAndRenderUsers() {
        try {
            const data = await apiFetch('/api/v1/users');
            usersTableBody.innerHTML = ''; // Clear table
            data.users.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.id}</td>
                    <td>${user.email}</td>
                    <td>${user.role}</td>
                    <td>${new Date(user.created_at).toLocaleString()}</td>
                    <td>
                        <button class="btn-delete-user" data-id="${user.id}" data-email="${user.email}">Delete</button>
                    </td>
                `;
                usersTableBody.appendChild(row);
            });

            // Add event listeners to new delete buttons
            document.querySelectorAll('.btn-delete-user').forEach(button => {
                button.addEventListener('click', handleDeleteUser);
            });

        } catch (error) {
            errorMessageDiv.textContent = `Error loading users: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    async function handleAddUser(event) {
        event.preventDefault();
        errorMessageDiv.classList.add('hidden');
        const formData = new FormData(addUserForm);
        const body = {
            email: formData.get('email'),
            password: formData.get('password'),
            role: formData.get('role'),
        };

        try {
            await apiFetch('/api/v1/users', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            addUserForm.reset();
            await loadAndRenderUsers();
        } catch (error) {
            errorMessageDiv.textContent = `Failed to add user: ${error.message}`;
            errorMessageDiv.classList.remove('hidden');
        }
    }

    async function handleDeleteUser(event) {
        const userId = event.target.dataset.id;
        const userEmail = event.target.dataset.email;
        if (confirm(`Are you sure you want to delete user ${userEmail} (ID: ${userId})?`)) {
            try {
                await apiFetch(`/api/v1/users/${userId}`, { method: 'DELETE' });
                await loadAndRenderUsers();
            } catch (error) {
                errorMessageDiv.textContent = `Failed to delete user: ${error.message}`;
                errorMessageDiv.classList.remove('hidden');
            }
        }
    }

    addUserForm.addEventListener('submit', handleAddUser);

    // Initial load
    await loadAndRenderUsers();
}