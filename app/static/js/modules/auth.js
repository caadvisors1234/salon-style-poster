/**
 * Authentication Module
 */
import { TOKEN_KEY } from '../config.js';

/**
 * Stores the JWT token in local storage.
 * @param {string} token - The JWT token.
 */
export function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Retrieves the JWT token from local storage.
 * @returns {string|null} The JWT token or null if not found.
 */
export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Removes the JWT token from local storage.
 */
export function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
}

/**
 * Handles the logout process.
 */
export function logout() {
    removeToken();
    window.location.href = '/login';
}
