/**
 * SALON BOARD Style Poster - 共通JavaScriptファイル
 *
 * 現在、主要な機能はbase.htmlの<script>セクションに実装されています。
 * このファイルは将来的な拡張や追加機能のために用意されています。
 */

// 将来的な共通ユーティリティ関数をここに追加可能
// 例:
// - 日付フォーマット関数
// - バリデーション関数
// - 追加のUI操作関数
// など

/**
 * 日付を日本語形式でフォーマット
 * @param {string|Date} date - フォーマットする日付
 * @returns {string} フォーマットされた日付文字列
 */
function formatJapaneseDate(date) {
    const d = new Date(date);
    return d.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * ファイルサイズを人間が読みやすい形式でフォーマット
 * @param {number} bytes - バイト数
 * @returns {string} フォーマットされたファイルサイズ
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * デバウンス関数（検索入力などの連続イベント処理に使用）
 * @param {Function} func - 実行する関数
 * @param {number} wait - 待機時間（ミリ秒）
 * @returns {Function} デバウンス処理された関数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// グローバルに公開（必要に応じて）
if (typeof window !== 'undefined') {
    window.formatJapaneseDate = formatJapaneseDate;
    window.formatFileSize = formatFileSize;
    window.debounce = debounce;
}
