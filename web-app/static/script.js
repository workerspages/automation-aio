function showAddTaskModal() {
    document.getElementById('taskModal').style.display = 'block';
    document.getElementById('modalTitle').textContent = '添加任务';
    document.getElementById('taskForm').reset();
}

function closeModal() {
    document.getElementById('taskModal').style.display = 'none';
}

document.getElementById('taskForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        name: document.getElementById('taskName').value,
        script_path: document.getElementById('scriptPath').value,
        cron_expression: document.getElementById('cronExpression').value,
        enabled: true
    };
    
    const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    
    if (response.ok) {
        location.reload();
    }
});

async function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) return;
    
    const response = await fetch(`/api/tasks/${taskId}`, {
        method: 'DELETE'
    });
    
    if (response.ok) {
        location.reload();
    }
}
