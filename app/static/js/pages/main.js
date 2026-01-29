/**
 * Main Page Logic
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
    UNPUBLISH_PROCESSING: '非掲載処理中',
    UNPUBLISH_COMPLETED: '非掲載完了',
    UNPUBLISH_ERROR: '非掲載エラー',
    CANCELLING: 'キャンセル処理',
    CANCELLED: 'キャンセル済み',
    FAILED: 'タスク失敗',
    COMPLETED: 'タスク完了'
};

// --- Initialization ---

async function init() {
    try {
        await requestNotificationPermission();
        await loadSettings();
        await checkTaskStatus();

        // D&D Setup
        setupDragAndDrop('drop-zone-data', 'style_data_file', 'file-name-data', false);
        setupDragAndDrop('drop-zone-images', 'image_files', 'preview-area-images', true);

        // Event Listeners
        const taskForm = document.getElementById('task-form');
        if (taskForm) {
            taskForm.addEventListener('submit', handleTaskSubmit);
        }

        const cancelBtn = document.getElementById('cancel-task-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', handleCancelTask);
        }

        const newTaskBtn = document.getElementById('new-task-btn');
        if (newTaskBtn) {
            newTaskBtn.addEventListener('click', handleNewTask);
        }

        // Template Example Toggle - if specific button exists
        // (Note: in index.html, onclick="toggleTemplateExample" might be used. We need to attach listener instead if possible, or expose global)
        // For module compatibility, it's better to attach listeners if element IDs are known.
        // Or export functions and attach to window if we can't change HTML structure easily yet.
        // Assuming there is a toggle button? The snippet showed `function toggleTemplateExample`.

    } catch (error) {
        console.error('Initialization error:', error);
        showAlert(error.message, 'danger');
    }
}

// Start initialization
init();


// --- Helper Functions ---

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
        const select = document.getElementById('setting_id');

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
        const errorRepSec = document.getElementById('error-report-section');
        const manualUpSec = document.getElementById('manual-upload-section');
        if (errorRepSec) errorRepSec.classList.add('hidden');
        if (manualUpSec) manualUpSec.classList.add('hidden');
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
        // errorItems.length は後で設定されるため、ここでは0を設定
        if (errorCountResult) errorCountResult.textContent = '0';

        // エラーをカテゴリ別に分類
        // 手動対応が必要: INPUT_FAILED, IMAGE_UPLOAD_ABORTED, ACCESS_CONGESTION
        const manualRequiredCategories = ['INPUT_FAILED', 'IMAGE_UPLOAD_ABORTED', 'ACCESS_CONGESTION'];

        // manual_uploads + errorsから手動対応項目を抽出
        const manualItems = [];
        const errorItems = [];

        // manual_uploadsを追加
        (report.manual_uploads || []).forEach(item => {
            manualItems.push(item);
        });

        // errorsから手動対応が必要なものを抽出
        (report.errors || []).forEach(error => {
            if (error.error_category && manualRequiredCategories.includes(error.error_category)) {
                manualItems.push(error);
            } else {
                errorItems.push(error);
            }
        });

        // エラーカウントを設定（errorItems.length を使用）
        if (errorCountResult) errorCountResult.textContent = errorItems.length;

        // 手動対応セクションの表示
        if (manualList) manualList.innerHTML = '';
        if (manualItems.length > 0) {
            if (manualSection) manualSection.classList.remove('hidden');
            if (manualCountBadge) manualCountBadge.textContent = `${manualItems.length}件`;
            manualItems.forEach((item, index) => {
                const row = document.createElement('tr');
                // 対象項目: image_nameがあれば画像名、なければfield
                const targetItem = item.image_name || item.field || '-';
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${item.style_name || '-'}</td>
                    <td>${targetItem}</td>
                    <td>${item.reason || ''}</td>
                `;
                if (manualList) manualList.appendChild(row);
            });
        } else {
            if (manualSection) manualSection.classList.add('hidden');
            if (manualCountBadge) manualCountBadge.textContent = '0件';
        }

        // エラーレポートセクションの表示（手動対応以外のエラー）
        if (errorItems.length > 0) {
            errorItems.forEach((error, index) => {
                const errorItem = document.createElement('div');
                errorItem.className = 'error-item';

                const screenshotHtml = error.screenshot_url ? `
                    <div class="error-screenshot">
                        <strong>スクリーンショット:</strong>
                        <div class="screenshot-thumbnail-container">
                            <img
                                src="${error.screenshot_url}"
                                alt="エラーのスクリーンショット（クリックで拡大）"
                                class="screenshot-thumbnail"
                                data-url="${error.screenshot_url}"
                                role="button"
                                tabindex="0"
                                aria-label="スクリーンショットを拡大表示"
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
                // Add click and keyboard listeners for screenshot
                const img = errorItem.querySelector('.screenshot-thumbnail');
                if (img) {
                    const openModal = () => openScreenshotModal(error.screenshot_url);
                    img.addEventListener('click', openModal);
                    img.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            openModal();
                        }
                    });
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

// --- Event Handlers ---

async function handleTaskSubmit(e) {
    e.preventDefault();

    const formData = new FormData(e.target);

    showLoading();

    try {
        await apiCallFormData('/api/v1/tasks/style-post', formData);

        hideLoading();
        showAlert('タスクを開始しました', 'success');

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
        const form = document.getElementById('task-form');
        if (form) form.reset();

        const fileNameData = document.getElementById('file-name-data');
        if (fileNameData) fileNameData.textContent = '';

        const previewArea = document.getElementById('preview-area-images');
        if (previewArea) previewArea.innerHTML = '';
    } catch (error) {
        showAlert(error.message, 'danger');
    }
}


// --- Drag & Drop Utils ---
// (Refactored to be cleaner)
function setupDragAndDrop(dropZoneId, inputId, previewId, isMultiple) {
    const dropZone = document.getElementById(dropZoneId);
    const input = document.getElementById(inputId);
    if (!dropZone || !input) return;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', handleDrop, false);

    input.addEventListener('change', function () {
        handleFiles(this.files);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            const dataTransfer = new DataTransfer();
            if (isMultiple) {
                Array.from(files).forEach(file => dataTransfer.items.add(file));
            } else {
                dataTransfer.items.add(files[0]);
            }
            input.files = dataTransfer.files;
            handleFiles(files);
        }
    }

    function handleFiles(files) {
        const previewArea = document.getElementById(previewId);
        if (!previewArea) return;

        previewArea.innerHTML = '';

        if (!files || files.length === 0) return;

        if (isMultiple) {
            let imageCount = 0;
            Array.from(files).forEach(file => {
                if (file.type.startsWith('image/')) {
                    imageCount++;
                    const reader = new FileReader();
                    reader.readAsDataURL(file);
                    reader.onloadend = function () {
                        const div = document.createElement('div');
                        div.className = 'preview-item';
                        div.innerHTML = `
                                  <img src="${reader.result}" alt="${file.name}">
                                  <div class="preview-item-name">${file.name}</div>
                             `;
                        previewArea.appendChild(div);
                    }
                }
            });
            if (imageCount === 0 && files.length > 0) {
                previewArea.textContent = `${files.length}個のファイルを選択中（画像なし）`;
            }
        } else {
            if (files.length > 0) {
                const file = files[0];
                previewArea.textContent = `選択中: ${file.name} (${formatBytes(file.size)})`;
            }
        }
    }
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

// Expose simple toggle function to window if necessary,
// OR better: attach event listener in init()
// But "Template Example" button logic wasn't fully visible in snippets.
// Assuming it has an ID, we can do it in init.
// If it's inline like onclick="toggleTemplateExample(event)", we need to export it or move to listener.
// I'll export it just in case, and attach to window.
window.toggleTemplateExample = function (e) {
    if (e) e.preventDefault();
    const example = document.getElementById('template-example');
    if (example) example.classList.toggle('hidden');
};
