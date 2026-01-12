/**
 * Settings Page Logic
 */
import { apiCall } from '../modules/api.js';
import { showAlert, showLoading, hideLoading } from '../modules/ui.js';

let editingSettingId = null;

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await apiCall('/api/v1/auth/me'); // Token check
        await loadSettings();
        setupEventListeners();
    } catch (error) {
        console.error('Initialization error:', error);
        showAlert(error.message, 'danger');
    }
});

function setupEventListeners() {
    // Add Setting Button
    const addBtn = document.getElementById('add-setting-btn');
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            editingSettingId = null;
            document.getElementById('modal-title').textContent = '新規設定を追加';
            const form = document.getElementById('setting-form');
            if (form) form.reset();
            document.getElementById('setting-id').value = '';
            document.getElementById('sb_password').required = true;
            openModal();
        });
    }

    // Modal Events
    const modal = document.getElementById('setting-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'setting-modal') closeModal();
        });
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        const cancelBtn = modal.querySelector('.btn-secondary');
        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    }

    // Submit Button
    const submitBtn = document.querySelector('#setting-modal .btn-primary'); // Assuming this is the submit button in footer
    // Actually the button in HTML has onclick="submitSetting()". 
    // We should attach listener and remove onclick from HTML later.
    // For now, let's attach listener to the button.
    // The HTML has `onclick="submitSetting()"` which refers to global function.
    // Since we are module, global scope is not polluted. We MUST modify HTML to remove onclick, OR attach listener here.
    // Replacing HTML is part of next step. Here we attach listener.
    if (submitBtn) {
        // Remove old onclick attribute in HTML refactoring.
        submitBtn.addEventListener('click', submitSetting);
    }
}


// Settings Logic

async function loadSettings() {
    try {
        const data = await apiCall('/api/v1/sb-settings/');
        const settings = data.settings || [];
        const tbody = document.getElementById('settings-tbody');
        const noSettings = document.getElementById('no-settings');

        if (tbody) tbody.innerHTML = '';

        if (settings.length === 0) {
            if (noSettings) noSettings.classList.remove('hidden');
            return;
        }

        if (noSettings) noSettings.classList.add('hidden');

        settings.forEach(setting => {
            const tr = document.createElement('tr');

            const salonInfo = setting.salon_id || setting.salon_name
                ? `ID: ${setting.salon_id || '-'}, 名前: ${setting.salon_name || '-'}`
                : '-';

            // Note: onclick="editSetting..." will fail because editSetting is not global.
            // Requirement: Use event delegation or attach listeners.
            // I will use innerHTML but then find buttons and attach listeners.

            tr.innerHTML = `
                <td>${setting.setting_name}</td>
                <td>${setting.sb_user_id}</td>
                <td>${salonInfo}</td>
                <td>
                    <button class="btn btn-secondary btn-edit" data-id="${setting.id}">
                        編集
                    </button>
                    <button class="btn btn-danger btn-delete" data-id="${setting.id}" data-name="${setting.setting_name}">
                        削除
                    </button>
                </td>
            `;
            if (tbody) tbody.appendChild(tr);
        });

        // Attach listeners for dynamic elements
        if (tbody) {
            tbody.querySelectorAll('.btn-edit').forEach(btn => {
                btn.addEventListener('click', () => editSetting(btn.dataset.id));
            });
            tbody.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', () => deleteSetting(btn.dataset.id, btn.dataset.name));
            });
        }

    } catch (error) {
        console.error('Failed to load settings:', error);
        showAlert(error.message, 'danger');
    }
}

async function editSetting(settingId) {
    try {
        const setting = await apiCall(`/api/v1/sb-settings/${settingId}`);
        editingSettingId = settingId;

        document.getElementById('modal-title').textContent = '設定を編集';
        document.getElementById('setting-id').value = setting.id;
        document.getElementById('setting_name').value = setting.setting_name;
        document.getElementById('sb_user_id').value = setting.sb_user_id;
        document.getElementById('salon_id').value = setting.salon_id || '';
        document.getElementById('salon_name').value = setting.salon_name || '';

        const sbPass = document.getElementById('sb_password');
        sbPass.value = '';
        sbPass.required = false;

        openModal();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

async function deleteSetting(settingId, settingName) {
    if (!confirm(`「${settingName}」を削除してもよろしいですか？`)) {
        return;
    }

    try {
        await apiCall(`/api/v1/sb-settings/${settingId}`, { method: 'DELETE' });
        showAlert('設定を削除しました', 'success');
        await loadSettings();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

async function submitSetting() {
    const form = document.getElementById('setting-form');

    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const data = {
        setting_name: document.getElementById('setting_name').value,
        sb_user_id: document.getElementById('sb_user_id').value,
        salon_id: document.getElementById('salon_id').value || null,
        salon_name: document.getElementById('salon_name').value || null
    };

    const password = document.getElementById('sb_password').value;
    if (password) {
        data.sb_password = password;
    }

    showLoading();

    try {
        if (editingSettingId) {
            // Update
            await apiCall(`/api/v1/sb-settings/${editingSettingId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
            showAlert('設定を更新しました', 'success');
        } else {
            // Create
            await apiCall('/api/v1/sb-settings/', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            showAlert('設定を追加しました', 'success');
        }

        hideLoading();
        closeModal();
        await loadSettings();
    } catch (error) {
        hideLoading();
        showAlert(error.message, 'danger');
    }
}


function openModal() {
    const modal = document.getElementById('setting-modal');
    if (modal) modal.classList.add('active');
}

function closeModal() {
    const modal = document.getElementById('setting-modal');
    if (modal) modal.classList.remove('active');
}
