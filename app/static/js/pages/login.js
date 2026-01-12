/**
 * Login Page Logic
 */
import { saveToken, getToken } from '../modules/auth.js';

// Initialization
function init() {
    // 既にログイン済みの場合はメインページにリダイレクト
    if (getToken()) {
        window.location.href = '/main';
        return;
    }

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const errorMessageDiv = document.getElementById('error-message');
    if (errorMessageDiv) {
        errorMessageDiv.classList.add('hidden');
        errorMessageDiv.textContent = '';
    }

    const formData = new FormData(e.target);
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
            throw new Error(errorData.detail || 'ログインに失敗しました');
        }

        const data = await response.json();
        saveToken(data.access_token);
        window.location.href = '/main';

    } catch (error) {
        if (errorMessageDiv) {
            errorMessageDiv.textContent = error.message;
            errorMessageDiv.classList.remove('hidden');
        } else {
            alert(error.message);
        }
    }
}

// Start
init();
