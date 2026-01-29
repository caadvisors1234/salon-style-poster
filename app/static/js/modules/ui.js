/**
 * UI Helper Functions & Components
 */
import { getToken, logout } from './auth.js';
import { apiCall } from './api.js';

// --- Toast Notification ---

/**
 * Shows an alert/toast message.
 * @param {string} message - The message to display.
 * @param {string} type - The alert type (success, danger, warning, info).
 */
export function showAlert(message, type = 'info') {
    let alertContainer = document.getElementById('alert-container');

    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'alert-container';
        alertContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        document.body.appendChild(alertContainer);
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    // Using inline styles for now to ensure visibility even if CSS classes missing, 
    // though style.css should handle alert classes if available or we rely on bootstrap-like utility.
    // Enhanced style for better look
    alert.style.cssText = 'margin-bottom: 10px; padding: 12px 20px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: space-between; min-width: 250px; animation: slideIn 0.3s ease-out;';

    // Add close button
    alert.innerHTML = `
        <span>${message}</span>
        <button type="button" style="background:none; border:none; margin-left: 10px; cursor:pointer; font-size: 1.2em; line-height: 1;">&times;</button>
    `;

    // Color mapping
    const colors = {
        success: { bg: '#d4edda', text: '#155724', border: '#c3e6cb' },
        danger: { bg: '#f8d7da', text: '#721c24', border: '#f5c6cb' },
        warning: { bg: '#fff3cd', text: '#856404', border: '#ffeeba' },
        info: { bg: '#d1ecf1', text: '#0c5460', border: '#bee5eb' }
    };
    const theme = colors[type] || colors.info;
    alert.style.backgroundColor = theme.bg;
    alert.style.color = theme.text;
    alert.style.border = `1px solid ${theme.border}`;

    // Close button event
    const closeBtn = alert.querySelector('button');
    closeBtn.onclick = () => {
        alert.style.animation = 'fadeOut 0.3s ease-in';
        setTimeout(() => alert.remove(), 290);
    };

    alertContainer.appendChild(alert);

    // Auto-remove
    setTimeout(() => {
        if (alert.parentNode) {
            alert.style.animation = 'fadeOut 0.3s ease-in';
            setTimeout(() => {
                alert.remove();
                if (alertContainer.children.length === 0) {
                    alertContainer.remove();
                }
            }, 290);
        }
    }, 5000);
}

// Ensure keyframe styles exists
const styleSheet = document.createElement("style");
styleSheet.innerText = `
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
`;
document.head.appendChild(styleSheet);


// --- Loading Overlay ---

/**
 * Shows a loading indicator.
 */
export function showLoading() {
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
            <div style="background: white; padding: 20px 40px; border-radius: 8px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
                <div style="border: 4px solid #f3f3f3; border-top: 4px solid var(--brand-color, #007bff); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                <div style="font-weight: bold; color: #333;">読み込み中...</div>
            </div>
        `;
        document.body.appendChild(loadingDiv);

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
export function hideLoading() {
    const loadingDiv = document.getElementById('loading-overlay');
    if (loadingDiv) {
        loadingDiv.style.display = 'none';
    }
}


// --- Header & Navigation ---

/**
 * Initializes the header navigation based on auth state.
 * @param {string} activePage - The current active page ID (e.g. 'main', 'settings').
 */
export async function setupHeader(activePage = '') {
    const nav = document.getElementById('header-nav');
    if (!nav) return;

    const token = getToken();

    // Elements logic from base.html
    const headerContent = document.querySelector('.header-content');
    const menuToggleButton = document.getElementById('menu-toggle');

    // Simple responsive sync logic
    const syncNavWithViewport = () => {
        if (window.innerWidth >= 768) {
            nav.classList.remove('is-open');
            nav.style.display = 'flex'; // Desktop: always show (flex layout)
            if (menuToggleButton) menuToggleButton.style.display = 'none';
        } else {
            nav.style.display = nav.classList.contains('is-open') ? 'flex' : 'none';
            if (menuToggleButton) menuToggleButton.style.display = 'block';
        }
    };

    window.addEventListener('resize', syncNavWithViewport);
    if (menuToggleButton) {
        menuToggleButton.addEventListener('click', () => {
            nav.classList.toggle('is-open'); // Fix: Match CSS class .is-open
            const isOpen = nav.classList.contains('is-open');
            menuToggleButton.setAttribute('aria-expanded', isOpen);
            // Mobile toggle logic
            nav.style.display = isOpen ? 'flex' : 'none';
        });
    }

    if (token) {
        try {
            const user = await apiCall('/api/v1/auth/me');

            const navLinks = [
                { href: '/main', text: 'スタイル投稿', id: 'main' },
                { href: '/unpublish', text: 'スタイル非掲載', id: 'unpublish' },
                { href: '/settings', text: '設定', id: 'settings' }
            ];

            if (user.role === 'admin') {
                navLinks.push({ href: '/admin/users', text: 'ユーザー管理', id: 'admin' });
            }

            // Generate HTML
            const linksHtml = navLinks.map(link =>
                `<a href="${link.href}" class="nav-link ${activePage === link.id ? 'active' : ''}">${link.text}</a>`
            ).join('');

            nav.innerHTML = `
                <div class="nav-links">
                    ${linksHtml}
                </div>
                <div class="nav-meta">
                    <span class="nav-email">${user.email}</span>
                    <button type="button" id="logout-btn" class="btn btn-secondary">ログアウト</button>
                </div>
            `;

            // Attach Logout Event
            const logoutBtn = document.getElementById('logout-btn');
            if (logoutBtn) {
                logoutBtn.addEventListener('click', logout);
            }

            if (menuToggleButton) menuToggleButton.classList.remove('hidden');

        } catch (error) {
            console.error('Failed to load user info:', error);
            if (menuToggleButton) menuToggleButton.classList.add('hidden');
            nav.innerHTML = '';

            // Redirect if token invalid and not on login page
            const currentPath = window.location.pathname;
            if (currentPath !== '/login' && currentPath !== '/') {
                logout(); // Clears token and redirects
            }
        }
    } else {
        // No token
        if (menuToggleButton) menuToggleButton.classList.add('hidden');
        nav.innerHTML = '';

        const currentPath = window.location.pathname;
        if (currentPath !== '/login' && currentPath !== '/') {
            window.location.href = '/login';
        }
    }

    // Initial sync
    syncNavWithViewport();
}

// --- Screenshot Modal ---

/**
 * Opens a modal to display the screenshot.
 * @param {string} imageUrl - The URL of the image to display.
 */
export function openScreenshotModal(imageUrl) {
    const modal = document.createElement('div');
    modal.className = 'screenshot-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'スクリーンショット表示');
    modal.innerHTML = `
        <div class="screenshot-modal-content">
            <span class="screenshot-modal-close" aria-label="閉じる" role="button" tabindex="0">&times;</span>
            <img src="${imageUrl}" alt="Error screenshot" class="screenshot-modal-image">
        </div>
    `;

    document.body.appendChild(modal);

    // モーダルを開いたときはフォーカスを閉じるボタンに移動
    const closeBtn = modal.querySelector('.screenshot-modal-close');
    closeBtn.focus();

    const closeModal = () => {
        document.body.removeChild(modal);
    };

    closeBtn.onclick = closeModal;

    // キーボード操作対応（Enter/Spaceで閉じる）
    closeBtn.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            closeModal();
        }
    };

    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };

    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}
