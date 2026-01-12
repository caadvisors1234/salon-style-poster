/**
 * API Communication Module
 */
import { getToken, removeToken } from './auth.js';

/**
 * A wrapper for the fetch API to include auth tokens and handle errors.
 * @param {string} url - The URL to fetch.
 * @param {object} options - The options for the fetch request.
 * @returns {Promise<any>} The response from the server.
 */
export async function apiCall(url, options = {}) {
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
export async function apiCallFormData(url, formData) {
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
