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
const splitRow     = document.getElementById('split-row');
const splitCheck   = document.getElementById('split-check');
const splitCount   = document.getElementById('split-count');
const splitSizeRow   = document.getElementById('split-size-row');
const splitSizeCheck = document.getElementById('split-size-check');
const splitSizeMb    = document.getElementById('split-size-mb');
const sizeEstimate   = document.getElementById('size-estimate');

const AUDIO_EXTS = ['flac','wav','mp3','ogg','m4a','m4b','aac','aiff'];
let inputDurationS = 0;  // total duration across all audio files
let inputBytes     = 0;  // total bytes across all audio files

// Mutually exclusive: ticking one un-ticks the other
splitCheck.addEventListener('change', () => {
    if (splitCheck.checked) splitSizeCheck.checked = false;
});
splitSizeCheck.addEventListener('change', () => {
    if (splitSizeCheck.checked) splitCheck.checked = false;
});

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
function fileExt(name) { return name.split('.').pop().toLowerCase(); }

function probeDuration(file) {
    return new Promise(resolve => {
        const url = URL.createObjectURL(file);
        const audio = new Audio();
        audio.preload = 'metadata';
        audio.onloadedmetadata = () => {
            URL.revokeObjectURL(url);
            resolve(isFinite(audio.duration) ? audio.duration : 0);
        };
        audio.onerror = () => { URL.revokeObjectURL(url); resolve(0); };
        audio.src = url;
    });
}

async function handleFiles(files) {
    currentFiles = files;
    const filenames = files.map(f => f.name);
    inputDurationS = 0;
    inputBytes = 0;
    sizeEstimate.classList.add('hidden');

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

    // Probe duration of all audio inputs in parallel (best-effort)
    const audioFiles = files.filter(f => AUDIO_EXTS.includes(fileExt(f.name)));
    if (audioFiles.length === files.length && audioFiles.length > 0) {
        const durations = await Promise.all(audioFiles.map(probeDuration));
        inputDurationS = durations.reduce((a, b) => a + b, 0);
        inputBytes = audioFiles.reduce((a, f) => a + f.size, 0);
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

function estimateOutputKbps(target) {
    if (target === 'mp3-vbr') return 245;
    if (target.startsWith('mp3-')) return parseInt(target.split('-')[1], 10);
    if (target.startsWith('m4b-')) return parseInt(target.split('-')[1], 10);
    if (target === 'm4b') {
        // stream copy → use measured input bitrate
        if (inputDurationS > 0 && inputBytes > 0) {
            return (inputBytes * 8) / inputDurationS / 1000;
        }
        return 0;
    }
    if (target === 'm4a')  return 256;
    if (target === 'ogg')  return 192;
    if (target === 'wav')  return 2116;  // 24-bit stereo @ 44.1k
    if (target === 'aiff') return 1411;  // 16-bit stereo @ 44.1k
    if (target === 'flac') return 1000;  // rough estimate
    return 0;
}

function updateSizeEstimate() {
    if (!selectedFormat || inputDurationS <= 0) {
        sizeEstimate.classList.add('hidden');
        return;
    }
    const kbps = estimateOutputKbps(selectedFormat);
    if (!kbps) {
        sizeEstimate.classList.add('hidden');
        return;
    }
    const outBytes = (inputDurationS * kbps * 1000) / 8;
    const deltaPct = ((outBytes - inputBytes) / inputBytes) * 100;
    const cls = deltaPct < -1 ? 'delta-smaller'
              : deltaPct >  1 ? 'delta-larger'
              : 'delta-neutral';
    const sign = deltaPct >= 0 ? '+' : '';
    sizeEstimate.innerHTML =
        `original: <strong>${formatBytes(inputBytes)}</strong> → ` +
        `estimated: <strong>${formatBytes(outBytes)}</strong> ` +
        `<span class="${cls}">(${sign}${deltaPct.toFixed(0)}%)</span>`;
    sizeEstimate.classList.remove('hidden');
}

function selectFormat(fmt, btn) {
    document.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedFormat = fmt;
    btnConvert.disabled = false;
    updateSizeEstimate();

    // Show merge option for multi-file docx/pptx/pdf targets
    const mergeable = ['docx', 'pptx', 'pdf'];
    if (currentFiles.length > 1 && mergeable.includes(fmt)) {
        mergeRow.classList.remove('hidden');
    } else {
        mergeRow.classList.add('hidden');
        mergeCheck.checked = false;
    }

    // Show split options for single m4b uploads (any audio target)
    const isSingleM4b = currentFiles.length === 1
                        && currentFiles[0].name.toLowerCase().endsWith('.m4b');
    if (isSingleM4b) {
        splitRow.classList.remove('hidden');
        splitSizeRow.classList.remove('hidden');
    } else {
        splitRow.classList.add('hidden');
        splitCheck.checked = false;
        splitSizeRow.classList.add('hidden');
        splitSizeCheck.checked = false;
    }
}

// ── Convert ──────────────────────────────────────────────────────
btnConvert.addEventListener('click', async () => {
    if (!currentFiles.length || !selectedFormat) return;

    const fd = new FormData();
    currentFiles.forEach(f => fd.append('file', f));
    fd.append('target_format', selectedFormat);
    if (mergeCheck.checked) fd.append('merge', '1');
    if (splitCheck.checked) {
        const n = Math.max(2, parseInt(splitCount.value, 10) || 5);
        fd.append('split_chapters', n);
    }
    if (splitSizeCheck.checked) {
        const mb = Math.max(1, parseInt(splitSizeMb.value, 10) || 250);
        fd.append('split_size_mb', mb);
    }

    setConverting(true);
    hideAlert();

    try {
        const res = await fetch('/api/convert', { method: 'POST', body: fd });

        if (!res.ok) {
            throw new Error(await parseApiError(res));
        }

        // Trigger download
        const blob = await res.blob();
        const cd   = res.headers.get('Content-Disposition') || '';
        const match = cd.match(/filename="?([^"]+)"?/);

        let name;
        if (currentFiles.length === 1) {
            const baseName = currentFiles[0].name.replace(/\.[^.]+$/, '');
            let ext = selectedFormat;
            if (selectedFormat.startsWith('mp3')) ext = 'mp3';
            else if (selectedFormat.startsWith('m4b')) ext = 'm4b';
            if (splitCheck.checked || splitSizeCheck.checked) {
                name = `${baseName}_split.zip`;
            } else {
                name = match && match[1].endsWith('.zip') ? `${baseName}.zip` : `${baseName}.${ext}`;
            }
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
        let message = err && err.message ? err.message : 'Unknown error';
        if (err instanceof TypeError) {
            message = 'Network/proxy error while waiting for conversion. Large files may need higher proxy timeouts.';
        }
        showAlert(`Error: ${message}`, 'error');
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
    splitRow.classList.add('hidden');
    splitCheck.checked = false;
    splitSizeRow.classList.add('hidden');
    splitSizeCheck.checked = false;
    sizeEstimate.classList.add('hidden');
    inputDurationS = 0;
    inputBytes = 0;
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

async function parseApiError(res) {
    let apiError = '';
    try {
        const payload = await res.json();
        if (payload && typeof payload.error === 'string') {
            apiError = payload.error;
        }
    } catch {
        // Response was not JSON.
    }

    if (res.status === 413) {
        return apiError || 'Upload exceeds MAX_FILE_SIZE on the server.';
    }
    if (res.status === 502 || res.status === 503 || res.status === 504) {
        return apiError || 'Conversion timed out in a reverse proxy/upstream layer.';
    }
    if (res.status === 408 || res.status === 524) {
        return apiError || 'Conversion request timed out before completion.';
    }
    return apiError || `HTTP ${res.status}`;
}

function formatBytes(bytes) {
    if (bytes < 1024)               return bytes.toFixed(0) + ' B';
    if (bytes < 1048576)            return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1048576)     return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / (1024 * 1048576)).toFixed(2) + ' GB';
}
