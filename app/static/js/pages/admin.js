/**
 * Admin Users Page Logic
 */
import { apiCall } from '../modules/api.js';
import { showAlert, showLoading, hideLoading } from '../modules/ui.js';

let currentUser = null;
let editingUserId = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        currentUser = await apiCall('/api/v1/auth/me');

        // Admin check
        if (currentUser.role !== 'admin') {
            showAlert('このページにアクセスする権限がありません', 'danger');
            setTimeout(() => {
                window.location.href = '/main';
            }, 2000);
            return;
        }

        await loadUsers();
        setupEventListeners();
    } catch (error) {
        console.error('Initialization error:', error);
        showAlert(error.message, 'danger');
    }
});

function setupEventListeners() {
    // Add User Button
    const addBtn = document.getElementById('add-user-btn');
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            editingUserId = null;
            document.getElementById('modal-title').textContent = '新規ユーザーを追加';
            const form = document.getElementById('user-form');
            if (form) form.reset();
            document.getElementById('user-id').value = '';
            document.getElementById('role').value = 'user';
            document.getElementById('is_active').checked = true;
            document.getElementById('password').required = true;
            openModal();
        });
    }

    // Modal Events
    const modal = document.getElementById('user-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'user-modal') closeModal();
        });
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        const cancelBtn = modal.querySelector('.btn-secondary');
        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    }

    // Submit Button
    // HTML has onclick="submitUser()", we attach listener here.
    const submitBtn = document.querySelector('#user-modal .btn-primary');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitUser);
    }
}


async function loadUsers() {
    try {
        const data = await apiCall('/api/v1/users/');
        const users = data.users || [];
        const tbody = document.getElementById('users-tbody');

        if (tbody) tbody.innerHTML = '';

        users.forEach(user => {
            const tr = document.createElement('tr');

            const roleBadge = user.role === 'admin'
                ? '<span class="badge badge-danger">admin</span>'
                : '<span class="badge badge-info">user</span>';

            const activeBadge = user.is_active
                ? '<span class="badge badge-success">有効</span>'
                : '<span class="badge badge-danger">無効</span>';

            const createdAt = new Date(user.created_at).toLocaleString('ja-JP');

            const isSelf = user.id === currentUser.id;

            tr.innerHTML = `
                <td>${user.id}</td>
                <td>${user.email}</td>
                <td>${roleBadge}</td>
                <td>${activeBadge}</td>
                <td>${createdAt}</td>
                <td>
                    <button class="btn btn-secondary btn-edit" data-id="${user.id}">
                        編集
                    </button>
                    ${!isSelf ? `
                    <button class="btn btn-danger btn-delete" data-id="${user.id}" data-email="${user.email}">
                        削除
                    </button>
                    ` : '<span class="text-muted">（自分）</span>'}
                </td>
            `;
            if (tbody) tbody.appendChild(tr);
        });

        // Attach listeners
        if (tbody) {
            tbody.querySelectorAll('.btn-edit').forEach(btn => {
                btn.addEventListener('click', () => editUser(btn.dataset.id));
            });
            tbody.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', () => deleteUser(btn.dataset.id, btn.dataset.email));
            });
        }
    } catch (error) {
        console.error('Failed to load users:', error);
        showAlert(error.message, 'danger');
    }
}

async function editUser(userId) {
    try {
        const user = await apiCall(`/api/v1/users/${userId}`);
        editingUserId = userId;

        document.getElementById('modal-title').textContent = 'ユーザーを編集';
        document.getElementById('user-id').value = user.id;
        document.getElementById('email').value = user.email;
        document.getElementById('role').value = user.role;
        document.getElementById('is_active').checked = user.is_active;

        const pass = document.getElementById('password');
        if (pass) {
            pass.value = '';
            pass.required = false;
        }

        openModal();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

async function deleteUser(userId, email) {
    if (!confirm(`ユーザー「${email}」を削除してもよろしいですか？\n\nこのユーザーに紐づくSALON BOARD設定もすべて削除されます。`)) {
        return;
    }

    try {
        await apiCall(`/api/v1/users/${userId}`, { method: 'DELETE' });
        showAlert('ユーザーを削除しました', 'success');
        await loadUsers();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}

async function submitUser() {
    const form = document.getElementById('user-form');

    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const data = {
        email: document.getElementById('email').value,
        role: document.getElementById('role').value,
        is_active: document.getElementById('is_active').checked
    };

    const password = document.getElementById('password').value;
    if (password) {
        data.password = password;
    }

    showLoading();

    try {
        if (editingUserId) {
            // Update
            await apiCall(`/api/v1/users/${editingUserId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
            showAlert('ユーザーを更新しました', 'success');
        } else {
            // Create
            if (!password) {
                throw new Error('パスワードは必須です');
            }
            await apiCall('/api/v1/users/', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            showAlert('ユーザーを追加しました', 'success');
        }

        hideLoading();
        closeModal();
        await loadUsers();
    } catch (error) {
        hideLoading();
        showAlert(error.message, 'danger');
    }
}

function openModal() {
    const modal = document.getElementById('user-modal');
    if (modal) modal.classList.add('active');
}

function closeModal() {
    const modal = document.getElementById('user-modal');
    if (modal) modal.classList.remove('active');
}
