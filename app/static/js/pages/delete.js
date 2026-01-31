/**
 * Delete Page Logic
 */
import { apiCall, apiCallFormData } from '../modules/api.js';
import { showAlert, showLoading, hideLoading, openScreenshotModal } from '../modules/ui.js';

let pollingInterval = null;
let lastErrorCount = 0;
let notificationPermission = 'default';

const stageLabelMap = {
    BROWSER_STARTING: 'ブラウザ起動準備',
    BROWSER_READY: 'ブラウザ起動完了',
    LOGIN_COMPLETED: 'ログイン完了',
    DATA_READY: 'データ読み込み完了',
    NAVIGATED: '投稿準備完了',
    STYLE_PROCESSING: 'スタイル処理中',
    STYLE_COMPLETED: 'スタイル処理完了',
    STYLE_ERROR: 'スタイル処理エラー',
    STYLE_WARNING: '手動対応が必要',
    SUMMARY: '処理完了',
    TARGET_READY: '対象確認完了',
    DELETE_PROCESSING: '削除処理中',
    DELETE_COMPLETED: '削除完了',
    DELETE_ERROR: '削除エラー',
    CANCELLING: 'キャンセル処理',
    CANCELLED: 'キャンセル済み',
    FAILED: 'タスク失敗',
    COMPLETED: 'タスク完了'
};

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await apiCall('/api/v1/auth/me');
        await requestNotificationPermission();
        await loadSettings();
        await checkTaskStatus();
        setupEventListeners();
    } catch (error) {
        console.error('Initialization error:', error);
        showAlert(error.message, 'danger');
    }
});

function setupEventListeners() {
    const form = document.getElementById('delete-form');
    if (form) form.addEventListener('submit', handleTaskSubmit);

    const cancelBtn = document.getElementById('cancel-task-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', handleCancelTask);

    const newTaskBtn = document.getElementById('new-task-btn');
    if (newTaskBtn) newTaskBtn.addEventListener('click', handleNewTask);
}

// --- Logic ---

function resolveStageLabel(detail) {
    if (!detail) return '';
    if (detail.stage_label) return detail.stage_label;
    if (detail.stage && stageLabelMap[detail.stage]) {
        return stageLabelMap[detail.stage];
    }
    return '進捗情報';
}

function formatDetailTimestamp(isoString) {
    if (!isoString) return '';
    const parsed = new Date(isoString);
    if (Number.isNaN(parsed.getTime())) return '';
    return parsed.toLocaleString('ja-JP');
}

function deriveStatusLabel(status) {
    if (!status) return '状態取得中...';
    const detailStatus = status.detail?.status;

    if (status.status === 'PROCESSING') {
        if (detailStatus === 'error') return 'エラーを処理中...';
        if (detailStatus === 'working') return '処理中...';
        if (detailStatus === 'info') return '準備中...';
        return '処理中...';
    }

    if (status.status === 'CANCELLING') {
        return '中止要求を処理中...';
    }

    if (status.status === 'SUCCESS') {
        return '完了しました';
    }

    if (status.status === 'FAILURE') {
        if (detailStatus === 'cancelled') {
            return 'ユーザーが中止しました';
        }
        return 'エラーで停止しました';
    }

    return '状態取得中...';
}


async function requestNotificationPermission() {
    if ('Notification' in window) {
        notificationPermission = await Notification.requestPermission();
    }
}

function sendNotification(title, body, options = {}) {
    if (notificationPermission === 'granted') {
        new Notification(title, {
            body: body,
            icon: '/static/favicon.ico',
            badge: '/static/favicon.ico',
            ...options
        });
    }
}

async function loadSettings() {
    try {
        const data = await apiCall('/api/v1/sb-settings/');
        const settings = data.settings || [];
        const select = document.getElementById('delete_setting_id');

        if (!select) return;

        while (select.options.length > 1) {
            select.remove(1);
        }

        if (settings.length === 0) {
            showAlert('SALON BOARD設定が登録されていません。設定ページから登録してください。', 'warning');
        }

        settings.forEach(setting => {
            const option = document.createElement('option');
            option.value = setting.id;
            option.textContent = setting.setting_name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function checkTaskStatus() {
    try {
        const status = await apiCall('/api/v1/tasks/status');

        if (status.status === 'PROCESSING' || status.status === 'CANCELLING') {
            showProgressSection(status);
            startPolling();
        } else if (status.status === 'SUCCESS' || status.status === 'FAILURE') {
            await showResultSection(status);
        }
    } catch (error) {
        showFormSection();
    }
}

function showFormSection() {
    const formSec = document.getElementById('task-form-section');
    const progSec = document.getElementById('task-progress-section');
    const resSec = document.getElementById('task-result-section');
    if (formSec) formSec.classList.remove('hidden');
    if (progSec) progSec.classList.add('hidden');
    if (resSec) resSec.classList.add('hidden');
}

function showProgressSection(status) {
    const formSec = document.getElementById('task-form-section');
    const progSec = document.getElementById('task-progress-section');
    const resSec = document.getElementById('task-result-section');
    if (formSec) formSec.classList.add('hidden');
    if (progSec) progSec.classList.remove('hidden');
    if (resSec) resSec.classList.add('hidden');

    const cancelButton = document.getElementById('cancel-task-btn');
    if (cancelButton) {
        cancelButton.disabled = false;
        cancelButton.textContent = 'タスクを中止';
    }

    updateProgress(status);
}

async function showResultSection(status) {
    const formSec = document.getElementById('task-form-section');
    const progSec = document.getElementById('task-progress-section');
    const resSec = document.getElementById('task-result-section');
    if (formSec) formSec.classList.add('hidden');
    if (progSec) progSec.classList.add('hidden');
    if (resSec) resSec.classList.remove('hidden');

    const successMessage = document.getElementById('success-message');
    const failureMessage = document.getElementById('failure-message');
    if (successMessage) successMessage.classList.add('hidden');
    if (failureMessage) {
        failureMessage.classList.add('hidden');
        failureMessage.textContent = 'タスクがエラーにより中断されました';
    }

    if (status.status === 'SUCCESS') {
        if (successMessage) successMessage.classList.remove('hidden');
    } else if (status.detail?.status === 'cancelled') {
        if (failureMessage) {
            failureMessage.textContent = 'ユーザー操作によりタスクを中止しました';
            failureMessage.classList.remove('hidden');
        }
    } else {
        if (failureMessage) failureMessage.classList.remove('hidden');
    }

    if (status.has_errors || (status.manual_upload_count && status.manual_upload_count > 0)) {
        await loadErrorReport();
    } else {
        const errorRep = document.getElementById('error-report-section');
        const manualUp = document.getElementById('manual-upload-section');
        if (errorRep) errorRep.classList.add('hidden');
        if (manualUp) manualUp.classList.add('hidden');
    }
}

function updateProgress(status) {
    const progress = status.progress;
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressItems = document.getElementById('progress-items');
    const progressStatus = document.getElementById('progress-status');
    const progressDetail = document.getElementById('progress-detail');
    const progressStage = document.getElementById('progress-stage');
    const progressUpdatedAt = document.getElementById('progress-updated-at');
    const progressMessage = document.getElementById('progress-message');
    const progressStyleWrapper = document.getElementById('progress-style-wrapper');
    const progressStyleName = document.getElementById('progress-style-name');

    if (progressBar) progressBar.style.width = `${progress}%`;
    if (progressText) progressText.textContent = `${progress}%`;
    if (progressItems) progressItems.textContent = `${status.completed_items} / ${status.total_items} 件完了`;
    if (progressStatus) progressStatus.textContent = deriveStatusLabel(status);

    const detail = status.detail;
    if (detail) {
        if (progressDetail) progressDetail.classList.remove('hidden');
        if (progressStage) progressStage.textContent = resolveStageLabel(detail);
        if (progressMessage) progressMessage.textContent = detail.message || '';
        const timestampText = formatDetailTimestamp(detail.updated_at);
        if (progressUpdatedAt) progressUpdatedAt.textContent = timestampText ? `更新: ${timestampText}` : '';

        if (detail.style_name || detail.style_number) {
            if (progressStyleWrapper) progressStyleWrapper.classList.remove('hidden');
            if (progressStyleName) progressStyleName.textContent = detail.style_name || `番号 ${detail.style_number}`;
        } else {
            if (progressStyleWrapper) progressStyleWrapper.classList.add('hidden');
            if (progressStyleName) progressStyleName.textContent = '';
        }
    } else {
        if (progressDetail) progressDetail.classList.add('hidden');
        if (progressStage) progressStage.textContent = '';
        if (progressMessage) progressMessage.textContent = '';
        if (progressUpdatedAt) progressUpdatedAt.textContent = '';
        if (progressStyleWrapper) progressStyleWrapper.classList.add('hidden');
        if (progressStyleName) progressStyleName.textContent = '';
    }

    const errorSummaryProgress = document.getElementById('error-summary-progress');
    const errorCountProgress = document.getElementById('error-count-progress');

    if (status.error_count > 0) {
        if (errorSummaryProgress) errorSummaryProgress.classList.remove('hidden');
        if (errorCountProgress) errorCountProgress.textContent = status.error_count;

        if (status.error_count > lastErrorCount) {
            const newErrors = status.error_count - lastErrorCount;
            sendNotification(
                'エラー発生',
                `${newErrors}件の新しいエラーが発生しました（合計${status.error_count}件）`,
                { tag: 'task-error' }
            );
        }
        lastErrorCount = status.error_count;
    } else {
        if (errorSummaryProgress) errorSummaryProgress.classList.add('hidden');
    }
}

function startPolling() {
    if (pollingInterval) return;

    pollingInterval = setInterval(async () => {
        try {
            const status = await apiCall('/api/v1/tasks/status');

            if (status.status === 'PROCESSING' || status.status === 'CANCELLING') {
                updateProgress(status);
            } else {
                stopPolling();
                lastErrorCount = 0;

                if (status.status === 'SUCCESS') {
                    sendNotification(
                        'タスク完了',
                        status.has_errors
                            ? `タスクが完了しました（エラー: ${status.error_count}件）`
                            : 'タスクが完了しました',
                        { tag: 'task-complete' }
                    );
                } else {
                    const isCancelled = status.detail?.status === 'cancelled';
                    sendNotification(
                        isCancelled ? 'タスク中止' : 'タスク失敗',
                        isCancelled ? 'タスクをキャンセルしました' : 'タスクがエラーにより中断されました',
                        { tag: isCancelled ? 'task-cancelled' : 'task-failed' }
                    );
                }

                await showResultSection(status);
            }
        } catch (error) {
            console.error('Polling error:', error);
            stopPolling();
        }
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

async function loadErrorReport() {
    try {
        const report = await apiCall('/api/v1/tasks/error-report');
        const errorList = document.getElementById('error-list');
        const errorSection = document.getElementById('error-report-section');
        const errorCountResult = document.getElementById('error-count-result');
        const manualSection = document.getElementById('manual-upload-section');
        const manualList = document.getElementById('manual-upload-list');
        const manualCountBadge = document.getElementById('manual-upload-count');

        if (errorList) errorList.innerHTML = '';
        if (errorCountResult) errorCountResult.textContent = report.total_errors;

        if (manualList) manualList.innerHTML = '';
        const manualUploads = report.manual_uploads || [];
        if (manualUploads.length > 0) {
            if (manualSection) manualSection.classList.remove('hidden');
            if (manualCountBadge) manualCountBadge.textContent = `${manualUploads.length}件`;
            manualUploads.forEach((item, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${item.style_name || '-'}</td>
                    <td>${item.image_name || '-'}</td>
                    <td>${item.reason || ''}</td>
                `;
                if (manualList) manualList.appendChild(row);
            });
        } else {
            if (manualSection) manualSection.classList.add('hidden');
            if (manualCountBadge) manualCountBadge.textContent = '0件';
        }

        const errors = report.errors || [];
        if (errors.length > 0) {
            errors.forEach((error, index) => {
                const errorItem = document.createElement('div');
                errorItem.className = 'error-item';

                // Reusing Screenshot Modal from UI module (need to import)

                const screenshotHtml = error.screenshot_url ? `
                    <div class="error-screenshot">
                        <strong>スクリーンショット:</strong>
                        <div class="screenshot-thumbnail-container">
                            <img
                                src="${error.screenshot_url}"
                                alt="Error screenshot"
                                class="screenshot-thumbnail"
                            >
                            <div class="screenshot-overlay">クリックで拡大</div>
                        </div>
                    </div>
                ` : '';

                errorItem.innerHTML = `
                    <div class="error-item-header">
                        <span class="error-number">エラー ${index + 1}</span>
                        <span class="error-row">行 ${error.row_number}</span>
                        <span class="error-style-name">${error.style_name}</span>
                    </div>
                    <div class="error-item-details">
                        <div class="error-field">
                            <strong>項目:</strong> ${error.field}
                        </div>
                        <div class="error-reason">
                            <strong>理由:</strong> ${error.reason}
                        </div>
                        ${screenshotHtml}
                    </div>
                `;
                // Add click listener
                const img = errorItem.querySelector('.screenshot-thumbnail');
                if (img) {
                    img.addEventListener('click', () => openScreenshotModal(error.screenshot_url));
                }

                if (errorList) errorList.appendChild(errorItem);
            });
            if (errorSection) errorSection.classList.remove('hidden');
        } else {
            if (errorSection) errorSection.classList.add('hidden');
        }
    } catch (error) {
        console.error('Failed to load error report:', error);
    }
}

async function handleTaskSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const start = Number(formData.get('range_start') || 0);
    const end = Number(formData.get('range_end') || 0);

    if (start <= 0 || end <= 0 || start > end) {
        showAlert('開始番号と終了番号を確認してください', 'warning');
        return;
    }

    // 除外番号のバリデーション
    const excludeInput = document.getElementById('exclude_numbers');
    const excludeText = excludeInput?.value ? excludeInput.value : '';
    const excludeSet = new Set();
    const invalidExcludes = [];

    if (excludeText.trim() !== '') {
        for (const token of excludeText.replace(/\n/g, ',').split(',')) {
            const trimmed = token.trim();
            if (trimmed) {
                const num = parseInt(trimmed, 10);
                if (isNaN(num)) {
                    showAlert(`除外番号「${trimmed}」は有効な数字ではありません`, 'warning');
                    return;
                }
                if (num < start || num > end) {
                    invalidExcludes.push(num);
                } else {
                    excludeSet.add(num);
                }
            }
        }
    }

    if (invalidExcludes.length > 0) {
        showAlert(
            `除外番号に範囲外(${start}〜${end})の番号が含まれています: ${invalidExcludes.join(', ')}`,
            'warning'
        );
        return;
    }

    const totalCount = end - start + 1;
    const actualCount = totalCount - excludeSet.size;

    // 確認ダイアログ
    const displayExcludeText = excludeText.trim() !== '' ? excludeText : 'なし';
    if (!confirm(
        `削除タスクを開始します\n\n` +
        `開始番号: ${start}\n` +
        `終了番号: ${end}\n` +
        `除外番号: ${displayExcludeText}\n` +
        `対象件数: ${actualCount}件\n\n` +
        `よろしいですか？`
    )) {
        return;
    }

    showLoading();
    try {
        await apiCallFormData('/api/v1/tasks/style-delete', formData);
        hideLoading();
        showAlert('削除タスクを開始しました', 'success');
        await checkTaskStatus();
    } catch (error) {
        hideLoading();
        showAlert(error.message, 'danger');
    }
}

async function handleCancelTask(event) {
    const cancelButton = event.currentTarget;
    const originalText = cancelButton.textContent;

    if (!confirm('本当にタスクを即座に中止しますか？\n実行中の処理は強制終了されます。')) {
        return;
    }

    cancelButton.disabled = true;
    cancelButton.textContent = '中止リクエスト送信中...';

    try {
        await apiCall('/api/v1/tasks/cancel', { method: 'POST' });
        showAlert('タスクの中止を要求しました', 'info');
        await checkTaskStatus();
    } catch (error) {
        showAlert(error.message, 'danger');
    } finally {
        cancelButton.disabled = false;
        cancelButton.textContent = originalText;
    }
}

async function handleNewTask() {
    try {
        await apiCall('/api/v1/tasks/finished-task', { method: 'DELETE' });
        showFormSection();
        const form = document.getElementById('delete-form');
        if (form) form.reset();
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}
