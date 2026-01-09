let currentTaskId = null;
let currentFolder = 'downloads'; // 'downloads' or 'autokey'
let editorInstance = null; // CodeMirror instance

// 切换调度模式输入的显示/隐藏
function toggleScheduleInputs() {
    const cronGroup = document.getElementById('cronInputGroup');
    if (!cronGroup) return;

    const typeRadio = document.querySelector('input[name="scheduleType"]:checked');
    const type = typeRadio ? typeRadio.value : 'cron';

    const randomGroup = document.getElementById('randomInputGroup');
    const cronInput = document.getElementById('cronExpression');
    const startInput = document.getElementById('randomStart');
    const endInput = document.getElementById('randomEnd');

    if (type === 'random') {
        cronGroup.classList.add('hidden');
        randomGroup.classList.remove('hidden');
        if (cronInput) cronInput.required = false;
        if (startInput) startInput.required = true;
        if (endInput) endInput.required = true;
    } else {
        cronGroup.classList.remove('hidden');
        randomGroup.classList.add('hidden');
        if (cronInput) cronInput.required = true;
        if (startInput) startInput.required = false;
        if (endInput) endInput.required = false;
    }
}

function openAddModal() {
    currentTaskId = null;
    document.getElementById('modalTitle').textContent = '添加任务';
    document.getElementById('taskForm').reset();
    document.getElementById('taskId').value = '';

    const cronRadio = document.querySelector('input[name="scheduleType"][value="cron"]');
    if (cronRadio) cronRadio.checked = true;
    toggleScheduleInputs();

    updateScriptOptions().then(() => {
        document.getElementById('taskModal').style.display = 'block';
    });
}

function updateScriptOptions(selectedValue = null) {
    return fetch('/api/scripts')
        .then(r => r.json())
        .then(scripts => {
            const select = document.getElementById('scriptPath');
            select.innerHTML = '<option value="">-- 选择脚本 --</option>';
            scripts.forEach(script => {
                const option = document.createElement('option');
                option.value = script.path;
                option.textContent = script.name;
                if (selectedValue && script.path === selectedValue) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
        })
        .catch(e => console.error('Failed to load scripts:', e));
}

function editTask(taskId) {
    currentTaskId = taskId;
    document.getElementById('modalTitle').textContent = '编辑任务';

    fetch(`/api/tasks/${taskId}`)
        .then(response => response.json())
        .then(task => {
            document.getElementById('taskId').value = task.id;
            document.getElementById('taskName').value = task.name;

            // 动态加载脚本列表并回显
            updateScriptOptions(task.script_path);
            document.getElementById('scriptPath').value = task.script_path;

            const scheduleType = task.schedule_type || 'cron';
            const radio = document.querySelector(`input[name="scheduleType"][value="${scheduleType}"]`);
            if (radio) radio.checked = true;

            if (scheduleType === 'random') {
                document.getElementById('randomStart').value = task.random_start || '';
                document.getElementById('randomEnd').value = task.random_end || '';
                document.getElementById('cronExpression').value = task.cron_expression || '';
            } else {
                document.getElementById('cronExpression').value = task.cron_expression || '';
                document.getElementById('randomStart').value = '';
                document.getElementById('randomEnd').value = '';
            }

            toggleScheduleInputs();
            document.getElementById('taskModal').style.display = 'block';
        })
        .catch(error => {
            alert('获取任务详情失败: ' + error);
        });
}

function saveTask(event) {
    event.preventDefault();

    const taskId = document.getElementById('taskId').value;
    const scheduleTypeRadio = document.querySelector('input[name="scheduleType"]:checked');
    const scheduleType = scheduleTypeRadio ? scheduleTypeRadio.value : 'cron';

    const data = {
        name: document.getElementById('taskName').value,
        script_path: document.getElementById('scriptPath').value,
        enabled: true,
        schedule_type: scheduleType
    };

    if (scheduleType === 'random') {
        data.random_start = document.getElementById('randomStart').value;
        data.random_end = document.getElementById('randomEnd').value;
        data.cron_expression = "";
    } else {
        data.cron_expression = document.getElementById('cronExpression').value;
    }

    const url = taskId ? `/api/tasks/${taskId}` : '/api/tasks';
    const method = taskId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                closeModal('taskModal');
                location.reload();
            } else {
                alert('保存失败: ' + (result.error || '未知错误'));
            }
        })
        .catch(error => alert('保存失败: ' + error));
}

// --- 任务操作 ---
function runTaskNow(taskId) {
    if (!confirm('确定立即执行此任务吗？')) return;
    fetch(`/api/tasks/${taskId}/run`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) alert('任务已加入队列');
            else alert('执行失败: ' + res.error);
        });
}

function deleteTask(taskId) {
    if (!confirm('确定删除此任务吗？')) return;
    fetch(`/api/tasks/${taskId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
            if (res.success) location.reload();
            else alert('删除失败: ' + res.error);
        });
}

function toggleTask(taskId) {
    fetch(`/api/tasks/${taskId}/toggle`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) location.reload();
            else alert('操作失败: ' + res.error);
        });
}

// --- Cron Helper ---
function setCron(expression) {
    const input = document.getElementById('cronExpression');
    if (input) {
        input.value = expression;
        updateCronHelp(expression);
    }
}

function updateCronHelp(expression) {
    const helpText = document.getElementById('cronHelp');
    if (!helpText) return;
    const descriptions = {
        '*/5 * * * *': '每5分钟执行一次',
        '0 * * * *': '每小时整点执行',
        '0 9 * * *': '每天上午9点执行',
        '0 9,12,18 * * *': '每天上午9/12/18点执行',
        '0 0 * * 1': '每周一午夜执行',
        '0 0 * * *': '每天午夜执行',
        '0 12 * * *': '每天中午12点执行'
    };
    helpText.textContent = descriptions[expression] || '自定义 Cron 表达式';
}

// --- 脚本管理器与编辑器 ---

function openFileManager() {
    currentFolder = 'downloads';
    switchFolder('downloads');
    document.getElementById('fileManagerModal').style.display = 'block';
}

function switchFolder(folder) {
    currentFolder = folder;
    document.querySelectorAll('.folder-tab').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${folder}`).classList.add('active');

    const pathHint = folder === 'autokey'
        ? '正在查看: AutoKey 脚本 (系统级)'
        : '正在查看: 常规脚本 (Selenium/Python)';
    document.getElementById('current-path-hint').textContent = pathHint;

    loadFiles(folder);
}

function loadFiles(folder) {
    const container = document.getElementById('fileListContainer');
    container.innerHTML = '<div style="padding:20px;text-align:center;">加载中...</div>';

    fetch(`/api/files?folder=${folder}`)
        .then(r => r.json())
        .then(data => {
            if (!data.files || data.files.length === 0) {
                container.innerHTML = '<div style="padding:20px;text-align:center;color:#666;">暂无文件</div>';
                return;
            }

            let html = '';
            data.files.forEach(file => {
                html += `
                <div class="file-item">
                    <div class="file-info">
                        <span class="file-name">${file.name}</span>
                        <span class="file-meta">${file.modified} · ${(file.size / 1024).toFixed(1)} KB</span>
                    </div>
                    <div class="file-actions">
                        <button class="btn-secondary" style="padding:4px 10px;font-size:0.8em;" onclick="openEditor('${file.name}', '${folder}')">✎ 编辑</button>
                        <button class="btn-danger" style="padding:4px 10px;font-size:0.8em;" onclick="deleteScript('${file.name}', '${folder}')">🗑 删除</button>
                    </div>
                </div>`;
            });
            container.innerHTML = html;
        })
        .catch(e => {
            container.innerHTML = `<div style="padding:20px;color:red;">加载失败: ${e}</div>`;
        });
}

function createNewScript() {
    openEditor('', currentFolder);
}

function deleteScript(filename, folder) {
    if (!confirm(`确定要删除 ${filename} 吗？`)) return;

    fetch(`/api/files?folder=${folder}&filename=${encodeURIComponent(filename)}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
            if (res.success) loadFiles(folder);
            else alert('删除失败: ' + res.error);
        });
}

function initCodeMirror() {
    if (editorInstance) return;
    const textarea = document.getElementById('codeEditor');
    editorInstance = CodeMirror.fromTextArea(textarea, {
        mode: 'python',
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 4,
        matchBrackets: true
    });
}

function openEditor(filename, folder) {
    document.getElementById('editorFolder').value = folder;
    document.getElementById('editorFilename').value = filename;

    const nameDisplay = document.getElementById('editorFilenameDisplay');
    nameDisplay.value = filename;
    nameDisplay.disabled = !!filename;

    document.getElementById('editorTitle').textContent = filename ? '编辑脚本' : '新建脚本';
    document.getElementById('editorModal').style.display = 'block';

    setTimeout(() => {
        initCodeMirror();
        if (filename) {
            fetch(`/api/files/content?folder=${folder}&filename=${encodeURIComponent(filename)}`)
                .then(r => r.json())
                .then(res => {
                    if (res.content !== undefined) {
                        editorInstance.setValue(res.content);
                    } else {
                        alert('读取文件失败');
                        closeModal('editorModal');
                    }
                    editorInstance.refresh();
                });
        } else {
            // 默认 Python 模板
            editorInstance.setValue('# Python Automation Script\nimport time\n\nprint("Script started")\ntime.sleep(1)\nprint("Done")\n');
            editorInstance.refresh();
        }
    }, 100);
}

function saveScriptContent() {
    const folder = document.getElementById('editorFolder').value;
    let filename = document.getElementById('editorFilenameDisplay').value.trim();
    const content = editorInstance.getValue();

    if (!filename) {
        alert('请输入文件名');
        return;
    }

    // === 关键修改：只保留 .py 和 .side 的自动补全 ===
    if (!filename.endsWith('.py') && !filename.endsWith('.side')) {
        filename += '.py';
    }

    fetch('/api/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            folder: folder,
            filename: filename,
            content: content
        })
    })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                alert('保存成功!');
                closeModal('editorModal');
                if (document.getElementById('fileManagerModal').style.display === 'block') {
                    loadFiles(folder);
                }
            } else {
                alert('保存失败: ' + res.error);
            }
        })
        .catch(e => alert('请求错误: ' + e));
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    if (modalId === 'taskModal') currentTaskId = null;
}

window.onclick = function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const cronInput = document.getElementById('cronExpression');
    if (cronInput) {
        cronInput.addEventListener('input', function () {
            updateCronHelp(this.value);
        });
    }
    toggleScheduleInputs();
});
