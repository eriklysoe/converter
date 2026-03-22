'use strict';

const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const convertPanel = document.getElementById('convert-panel');
const fileIcon     = document.getElementById('file-icon');
const fileName     = document.getElementById('file-name');
const fileSize     = document.getElementById('file-size');
const fmtButtons   = document.getElementById('format-buttons');
const progressWrap = document.getElementById('progress-wrap');
const progressFill = document.getElementById('progress-fill');
const progressLabel= document.getElementById('progress-label');
const btnConvert   = document.getElementById('btn-convert');
const btnClear     = document.getElementById('btn-clear');
const alertBox     = document.getElementById('alert');
const mergeRow     = document.getElementById('merge-row');
const mergeCheck   = document.getElementById('merge-check');

let currentFiles  = [];
let selectedFormat = null;

// ── Drag & drop ─────────────────────────────────────────────────
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    if (files.length) handleFiles(files);
});
dropZone.addEventListener('click', (e) => {
    if (e.target.closest('.file-label')) return;
    fileInput.click();
});
fileInput.addEventListener('click', (e) => e.stopPropagation());
fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files);
    if (files.length) handleFiles(files);
});

// ── Clear ────────────────────────────────────────────────────────
btnClear.addEventListener('click', reset);

// ── File handling ─────────────────────────────────────────────────
async function handleFiles(files) {
    currentFiles = files;
    const filenames = files.map(f => f.name);

    // Show file info
    if (files.length === 1) {
        const ext = files[0].name.split('.').pop().toUpperCase();
        fileIcon.textContent = ext;
        fileName.textContent = files[0].name;
        fileSize.textContent = formatBytes(files[0].size);
    } else {
        fileIcon.textContent = files.length;
        fileName.textContent = `${files.length} files selected`;
        const totalSize = files.reduce((sum, f) => sum + f.size, 0);
        fileSize.textContent = formatBytes(totalSize);
    }

    // Fetch valid output formats (intersection for all files)
    try {
        const res = await fetch('/api/formats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames })
        });
        const data = await res.json();
        renderFormats(data.output_formats || []);
    } catch {
        showAlert('Could not determine output formats.', 'error');
        return;
    }

    dropZone.classList.add('hidden');
    convertPanel.classList.remove('hidden');
    hideAlert();
}

function renderFormats(formats) {
    fmtButtons.innerHTML = '';
    selectedFormat = null;
    btnConvert.disabled = true;

    if (!formats.length) {
        fmtButtons.innerHTML = '<span style="font-family:var(--mono);font-size:0.8rem;color:var(--text-dim)">no supported conversions</span>';
        return;
    }

    formats.forEach(fmt => {
        const btn = document.createElement('button');
        btn.className = 'fmt-btn';
        btn.textContent = fmt.toUpperCase();
        btn.addEventListener('click', () => selectFormat(fmt, btn));
        fmtButtons.appendChild(btn);
    });
}

function selectFormat(fmt, btn) {
    document.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedFormat = fmt;
    btnConvert.disabled = false;

    // Show merge option for multi-file docx/pptx/pdf targets
    const mergeable = ['docx', 'pptx', 'pdf'];
    if (currentFiles.length > 1 && mergeable.includes(fmt)) {
        mergeRow.classList.remove('hidden');
    } else {
        mergeRow.classList.add('hidden');
        mergeCheck.checked = false;
    }
}

// ── Convert ──────────────────────────────────────────────────────
btnConvert.addEventListener('click', async () => {
    if (!currentFiles.length || !selectedFormat) return;

    const fd = new FormData();
    currentFiles.forEach(f => fd.append('file', f));
    fd.append('target_format', selectedFormat);
    if (mergeCheck.checked) fd.append('merge', '1');

    setConverting(true);
    hideAlert();

    try {
        const res = await fetch('/api/convert', { method: 'POST', body: fd });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: 'Unknown error' }));
            throw new Error(err.error || `HTTP ${res.status}`);
        }

        // Trigger download
        const blob = await res.blob();
        const cd   = res.headers.get('Content-Disposition') || '';
        const match = cd.match(/filename="?([^"]+)"?/);

        let name;
        if (currentFiles.length === 1) {
            const baseName = currentFiles[0].name.replace(/\.[^.]+$/, '');
            name = match && match[1].endsWith('.zip') ? `${baseName}.zip` : `${baseName}.${selectedFormat}`;
        } else if (mergeCheck.checked) {
            name = `merged.${selectedFormat}`;
        } else {
            name = 'converted.zip';
        }

        const url = URL.createObjectURL(blob);
        const a   = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);

        const count = currentFiles.length;
        showAlert(`✓ Converted ${count} file${count > 1 ? 's' : ''} to ${selectedFormat.toUpperCase()} — download started`, 'success');
    } catch (err) {
        showAlert(`Error: ${err.message}`, 'error');
    } finally {
        setConverting(false);
    }
});

// ── Helpers ──────────────────────────────────────────────────────
function setConverting(active) {
    btnConvert.disabled = active;
    progressWrap.classList.toggle('hidden', !active);
    if (active) {
        progressFill.style.width = '0%';
        progressLabel.textContent = 'converting...';
        animateProgress();
    }
}

function animateProgress() {
    let pct = 0;
    const interval = setInterval(() => {
        pct = Math.min(pct + Math.random() * 8, 90);
        progressFill.style.width = pct + '%';
        if (!progressWrap.classList.contains('hidden') === false) clearInterval(interval);
    }, 300);
}

function reset() {
    currentFiles = [];
    selectedFormat = null;
    fileInput.value = '';
    convertPanel.classList.add('hidden');
    dropZone.classList.remove('hidden');
    fmtButtons.innerHTML = '';
    progressWrap.classList.add('hidden');
    mergeRow.classList.add('hidden');
    mergeCheck.checked = false;
    hideAlert();
}

function showAlert(msg, type) {
    alertBox.textContent = msg;
    alertBox.className = `alert ${type}`;
    alertBox.classList.remove('hidden');
}
function hideAlert() {
    alertBox.classList.add('hidden');
}

function formatBytes(bytes) {
    if (bytes < 1024)       return bytes + ' B';
    if (bytes < 1048576)    return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}
