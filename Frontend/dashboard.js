document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const emptyState = document.getElementById('empty-state');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loader = document.getElementById('loader');
    const loadingText = document.getElementById('loading-text');
    const resultsContainer = document.getElementById('results-container');
    const intro = document.getElementById('dashboard-intro');
    const overallSummary = document.getElementById('overall-summary');
    const evidenceGrid = document.getElementById('evidence-grid');
    const opinionsList = document.getElementById('opinions-list');
    const entitiesList = document.getElementById('entities-list');
    const relationsList = document.getElementById('relations-list');
    const finalSummary = document.getElementById('final-summary');
    const proofHashNode = document.getElementById('proof-hash');
    const blockchainNode = document.getElementById('blockchain-status');
    const progressText = document.getElementById('progress-percent');
    const instructionsInput = document.getElementById('user-instructions');

    // Chat Elements
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    const chatHistory = document.getElementById('chat-history');

    let selectedFiles = [];
    let currentCaseId = null;

    function safeCreateIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            try { window.lucide.createIcons(); } catch (e) { /* ignore */ }
        }
    }

    function bytesToKb(n) { return (n / 1024).toFixed(1) + ' KB'; }
    function escapeHtml(str) { return String(str || '').replace(/[&<>"'`=\/]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;','/':'&#x2F;','`':'&#x60;','=':'&#x3D;'})[s]); }

    // --- File Handling ---
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', (e) => { e.stopPropagation(); fileInput.value = null; fileInput.click(); });
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('border-red-500', 'bg-red-500/10'); });
        dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('border-red-500', 'bg-red-500/10'); });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault(); dropZone.classList.remove('border-red-500', 'bg-red-500/10');
            if (e.dataTransfer && e.dataTransfer.files) handleFiles(e.dataTransfer.files);
        });
        fileInput.addEventListener('change', (e) => { if (e.target && e.target.files) handleFiles(e.target.files); });
    }

    function handleFiles(files) {
        if (!files || files.length === 0) return;
        Array.from(files).forEach(file => {
            if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) selectedFiles.push(file);
        });
        renderFileList();
        updateUIState();
    }

    function renderFileList() {
        if (!fileList) return;
        fileList.innerHTML = '';
        if (selectedFiles.length === 0) {
            if (emptyState) { fileList.appendChild(emptyState); emptyState.style.display = 'block'; }
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        selectedFiles.forEach((file, index) => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between bg-black/40 p-3 rounded border border-gray-800 hover:border-gray-600 transition-colors';
            let iconName = 'file';
            if (file.type.startsWith('image/')) iconName = 'image';
            else if (file.type.startsWith('audio/')) iconName = 'mic';
            else if (file.type.startsWith('video/')) iconName = 'video';
            else if (file.name.endsWith('.pdf') || file.name.endsWith('.docx')) iconName = 'file-text';

            div.innerHTML = `
                <div class="flex items-center gap-3 overflow-hidden">
                    <i data-lucide="${iconName}" class="w-4 h-4 text-gray-400 shrink-0"></i>
                    <span class="font-mono text-sm text-gray-200 truncate">${escapeHtml(file.name)}</span>
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-xs text-gray-400">${bytesToKb(file.size)}</span>
                    <button data-remove-index="${index}" class="text-gray-500 hover:text-red-500 transition-colors remove-file-btn"><i data-lucide="x" class="w-4 h-4"></i></button>
                </div>`;
            fileList.appendChild(div);
        });
        safeCreateIcons();
        fileList.querySelectorAll('.remove-file-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const idx = parseInt(btn.getAttribute('data-remove-index'), 10);
                if (!Number.isNaN(idx)) removeFile(idx);
            });
        });
    }

    function removeFile(index) {
        if (index < 0 || index >= selectedFiles.length) return;
        selectedFiles.splice(index, 1);
        renderFileList();
        updateUIState();
    }

    function updateUIState() {
        if (!analyzeBtn) return;
        analyzeBtn.disabled = selectedFiles.length === 0;
        if (selectedFiles.length > 0) analyzeBtn.innerHTML = `<span>SCAN ${selectedFiles.length} FILE${selectedFiles.length>1?'S':''}</span> <i data-lucide="activity" class="w-4 h-4"></i>`;
        else analyzeBtn.innerHTML = `<span>INITIATE SCAN</span> <i data-lucide="activity" class="w-4 h-4"></i>`;
        safeCreateIcons();
    }

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (selectedFiles.length === 0) { fileInput.value = null; fileInput.click(); return; }
            await startAnalysis();
        });
    }

    // --- CHAT LOGIC (UPDATED) ---
    if (chatSendBtn && chatInput) {
        chatSendBtn.addEventListener('click', sendChatMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }

    async function sendChatMessage() {
        const query = chatInput.value.trim();
        if (!query) return;
        if (!currentCaseId) {
            appendChatMessage("System", "Error: No active case. Please run a scan first.", "text-red-400");
            return;
        }

        appendChatMessage("You", query, "text-blue-400");
        chatInput.value = '';
        
        const loadingId = "chat-loading-" + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = "text-gray-500 animate-pulse";
        loadingDiv.innerText = "Thinking...";
        chatHistory.appendChild(loadingDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            const resp = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, case_id: currentCaseId })
            });
            const data = await resp.json();
            
            const loader = document.getElementById(loadingId);
            if (loader) loader.remove();

            // FIXED: Check for data.response OR data.answer
            const reply = data.response || data.answer;
            if (reply) {
                appendChatMessage("AI Agent", reply, "text-green-400");
                if (data.sources && data.sources.length > 0) {
                    appendChatMessage("Sources", "Based on: " + data.sources.join(", "), "text-gray-600 text-xs");
                }
            } else if (data.error) {
                appendChatMessage("System", "Error: " + data.error, "text-red-400");
            } else {
                appendChatMessage("System", "No answer generated.", "text-red-400");
            }

        } catch (err) {
            const loader = document.getElementById(loadingId);
            if (loader) loader.remove();
            appendChatMessage("System", "Connection Error: " + err.message, "text-red-400");
        }
    }

    function appendChatMessage(sender, text, colorClass) {
        const div = document.createElement('div');
        div.className = "mb-2";
        div.innerHTML = `<span class="font-bold ${colorClass}">${escapeHtml(sender)}:</span> <span class="text-gray-300">${escapeHtml(text)}</span>`;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // --- ANALYSIS LOGIC ---
    async function startAnalysis() {
        if (loader) loader.classList.remove('hidden');
        if (intro) intro.classList.add('hidden');
        if (resultsContainer) resultsContainer.classList.add('hidden');
        setProgress(2); setLoadingText('Preparing payload...');

        const formData = new FormData();
        for (const f of selectedFiles) formData.append('files', f);
        const instr = (instructionsInput && instructionsInput.value) ? instructionsInput.value.trim() : '';
        formData.append('instructions', instr);

        let serverReport = null;
        let ok = false;
        try {
            setProgress(12); setLoadingText('Uploading files to Meta Agent...');
            const resp = await fetch('/verify_with_instructions', { method: 'POST', body: formData });
            if (resp.ok) {
                const json = await resp.json();
                ok = true;
                serverReport = json.meta_report || json.report || json;
            }
        } catch (err) { console.warn('verify_with_instructions failed:', err); }

        if (!ok) {
            try {
                setProgress(35); setLoadingText('Falling back to legacy verify endpoint...');
                const resp2 = await fetch('/verify', { method: 'POST', body: formData });
                if (resp2.ok) {
                    const json2 = await resp2.json();
                    serverReport = json2.report || json2;
                    ok = true;
                }
            } catch (err) { console.warn('Fallback failed:', err); }
        }

        await waitForProgressSimulation();
        setProgress(100); setLoadingText('Finalizing...');
        await sleep(300);

        if (loader) loader.classList.add('hidden');
        if (resultsContainer) resultsContainer.classList.remove('hidden');

        if (serverReport) {
            if (serverReport.meta_report) serverReport = serverReport.meta_report;
            renderMetaReport(serverReport);
        } else {
            renderSimulatedResults();
        }
        selectedFiles = []; renderFileList(); updateUIState();
    }

    function setProgress(n) { if (progressText) progressText.textContent = `${n}%`; }
    function setLoadingText(t) { if (loadingText) loadingText.textContent = t; }
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
    function waitForProgressSimulation(timeout=8000) {
        return new Promise((resolve) => {
            let cur = parseInt(progressText.textContent || '0', 10) || 0;
            const start = Date.now();
            const id = setInterval(() => {
                if (cur < 90) cur += Math.floor(Math.random()*6)+3;
                if (cur > 95) cur = 95;
                setProgress(Math.min(95, cur));
                if ((Date.now() - start) > timeout) { clearInterval(id); resolve(); }
            }, 120);
        });
    }

    function renderMetaReport(report) {
        if (report.session_id) currentCaseId = report.session_id; 
        else if (report.case_id) currentCaseId = report.case_id;
        else currentCaseId = "global"; 

        if (overallSummary) overallSummary.textContent = report.final_summary || report.overall_summary || "Analysis complete.";
        
        if (proofHashNode) proofHashNode.textContent = report.proof_hash ? `Proof: ${report.proof_hash}` : '';
        
        // FIXED: Blockchain Link Implementation
        if (blockchainNode) {
            const tx = report.blockchain_tx;
            if (tx && tx.tx_hash) {
                // Creates a clickable link to Sepolia Etherscan
                const explorerUrl = `https://sepolia.etherscan.io/tx/${tx.tx_hash}`;
                blockchainNode.innerHTML = `<span class="small-chip">Blockchain TX: <a class="text-blue-400 underline hover:text-blue-300" href="${explorerUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(tx.tx_hash)}</a></span>`;
            } else if (tx && tx.error) {
                blockchainNode.textContent = `Blockchain: ${tx.error}`;
            }
        }

        if (opinionsList) {
            opinionsList.innerHTML = '';
            const opinions = report.opinions || [];
            if (opinions.length === 0 && report.results) {
                (report.results || []).forEach(r => { opinions.push({file: r.file, opinion: r.report && r.report.verdict ? r.report.verdict : 'No opinion'}); });
            }
            opinions.forEach(o => {
                const li = document.createElement('div');
                li.className = 'bg-black/30 p-3 rounded border border-gray-800';
                li.innerHTML = `<div class="flex justify-between items-start"><div><div class="font-bold text-white">${escapeHtml(o.file)}</div><div class="text-xs text-gray-400 font-mono">${escapeHtml(o.opinion || '')}</div></div></div>`;
                opinionsList.appendChild(li);
            });
        }

        if (entitiesList) {
            entitiesList.innerHTML = '';
            (report.entities || []).forEach(ent => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>${escapeHtml(ent.name || ent.text)}</strong> <span class="text-xs text-gray-500 font-mono">(${escapeHtml(ent.type || 'OTHER')})</span>`;
                entitiesList.appendChild(li);
            });
        }
        if (relationsList) {
            relationsList.innerHTML = '';
            (report.relations || []).forEach(rel => {
                const li = document.createElement('li');
                li.className = 'text-sm';
                li.innerHTML = `<div class="font-mono text-xs text-gray-300">• <strong>${escapeHtml(rel.source||rel.entity_a)}</strong> — <em>${escapeHtml(rel.relation||rel.relationship)}</em> — <strong>${escapeHtml(rel.target||rel.entity_b)}</strong></div>`;
                relationsList.appendChild(li);
            });
        }
        
        if (evidenceGrid) {
            evidenceGrid.innerHTML = '';
            (report.results || []).forEach(item => renderEvidenceItem(item));
        }
        
        if (finalSummary) {
            let detailedLog = "--- DETAILED FORENSIC LOG ---\n\n";
            if (report.results && report.results.length > 0) {
                report.results.forEach(res => {
                    detailedLog += `📂 FILE: ${res.file}\n`;
                    if (res.type === 'image' && res.report) {
                        const score = res.report.tamperingPercentage || 0;
                        const verdict = res.report.verdict || "Unknown";
                        detailedLog += `   • Analysis Type: Deepfake Detection\n   • Verdict: ${verdict}\n   • Tamper Score: ${score}%\n`;
                    }
                    else if (res.type === 'video' && res.report) {
                        const fake = res.report.visual_analysis?.fake_ratio_percent || 0;
                        detailedLog += `   • Analysis Type: Video Frame Integrity\n   • Fake Frames Detected: ${fake}%\n`;
                    }
                    else {
                        const rep = res.report || {};
                        const danger = rep.misinformationAnalysis?.dangerScore || 0;
                        const flags = rep.misinformationAnalysis?.flags || [];
                        detailedLog += `   • Analysis Type: Content & Threat Scan\n   • Danger Score: ${danger}/100\n`;
                        if (rep.factCheckAgent && rep.factCheckAgent.verification_result) {
                            detailedLog += `   • Fact Check: ${rep.factCheckAgent.verification_result.substring(0, 100)}...\n`;
                        }
                    }
                    detailedLog += "\n-----------------------------------\n\n";
                });
                finalSummary.textContent = detailedLog;
            } else {
                finalSummary.textContent = report.final_summary || "Analysis Complete.";
            }
        }
        safeCreateIcons();
    }

    function renderEvidenceItem(item) {
        if (!evidenceGrid) return;
        const type = (item.type || '').toLowerCase();
        const file = item.file || 'Unknown';
        const report = item.report || {};
        let cardHTML = '';

        if (type === 'image') {
            const tamper = report.tamperingPercentage || 0;
            const verdict = report.verdict || 'Image analysis';
            cardHTML = `
                <div class="bg-card border border-gray-800 rounded-lg p-4 flex items-center justify-between">
                    <div>
                        <div class="font-bold text-white">${escapeHtml(file)}</div>
                        <div class="text-xs text-gray-400 font-mono">${escapeHtml(verdict)}</div>
                        <div class="text-sm text-gray-300 mt-2 line-clamp-2">${escapeHtml(report.explanation || '')}</div>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-orbitron ${tamper > 50 ? 'text-red-500' : 'text-green-500'}">${tamper.toFixed(1)}%</div>
                        <div class="text-xs text-gray-500 font-mono">TAMPER SCORE</div>
                    </div>
                </div>`;
        } else if (type === 'video') {
            const visuals = report.visual_analysis || {};
            const fakeRatio = visuals.fake_ratio_percent || 0;
            const maxScore = visuals.max_fake_score || 0;
            const duration = report.metadata ? report.metadata.duration_sec : 'N/A';
            cardHTML = `
                <div class="bg-card border border-gray-800 rounded-lg p-4">
                    <div class="flex items-start gap-4">
                        <div class="w-16 h-16 bg-black/40 rounded flex items-center justify-center shrink-0 border border-gray-700"><i data-lucide="video" class="w-8 h-8 text-gray-500"></i></div>
                        <div class="flex-1">
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="font-bold text-white">${escapeHtml(file)}</div>
                                    <div class="text-xs text-gray-400 font-mono">${escapeHtml(report.verdict || 'Video Analysis')}</div>
                                </div>
                                <div class="text-right">
                                    <div class="text-2xl font-orbitron ${fakeRatio > 0 ? 'text-red-500' : 'text-green-500'}">${fakeRatio}%</div>
                                    <div class="text-xs text-gray-500 font-mono">FAKE FRAMES</div>
                                </div>
                            </div>
                            <div class="mt-2 flex gap-4 text-xs text-gray-500 font-mono">
                                <span><strong class="text-gray-300">Max Score:</strong> ${maxScore}</span>
                                <span><strong class="text-gray-300">Duration:</strong> ${duration}s</span>
                            </div>
                        </div>
                    </div>
                </div>`;
        } else if (type === 'document' || type === 'audio') {
            const analysis = report.misinformationAnalysis || {};
            const danger = analysis.dangerScore || 0;
            const flags = analysis.flags ? analysis.flags.length : 0;
            const icon = type === 'audio' ? 'mic' : 'file-text';
            const label = type === 'audio' ? 'Audio Forensic Scan' : 'Document Forensic Scan';

            cardHTML = `
                <div class="bg-card border border-gray-800 rounded-lg p-4">
                    <div class="flex justify-between items-start">
                        <div class="flex items-center gap-3">
                             <div class="w-10 h-10 bg-black/40 rounded flex items-center justify-center border border-gray-700"><i data-lucide="${icon}" class="w-5 h-5 text-gray-500"></i></div>
                             <div>
                                <div class="font-bold text-white">${escapeHtml(file)}</div>
                                <div class="text-xs text-gray-400 font-mono">${label}</div>
                             </div>
                        </div>
                        <div class="text-right">
                             <div class="text-2xl font-orbitron ${danger > 50 ? 'text-red-500' : 'text-green-500'}">${danger}/100</div>
                             <div class="text-xs text-gray-500 font-mono">DANGER SCORE</div>
                        </div>
                    </div>
                    <div class="mt-3 text-sm text-gray-300 line-clamp-3 bg-black/20 p-2 rounded">${escapeHtml(report.summary || report.transcript?.text || 'No summary.')}</div>
                    <div class="mt-2 text-xs text-red-400 font-mono flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full ${flags > 0 ? 'bg-red-500' : 'bg-green-500'}"></div>
                        ${flags} Suspicious Flags found
                    </div>
                </div>`;
        } else {
             cardHTML = `
                <div class="bg-card border border-gray-800 rounded-lg p-4">
                    <div class="font-bold text-white">${escapeHtml(file)}</div>
                    <div class="text-xs text-gray-400">${escapeHtml(type)}</div>
                    <pre class="text-xs text-gray-500 mt-2 overflow-hidden h-16">${escapeHtml(JSON.stringify(report))}</pre>
                </div>`;
        }
        const div = document.createElement('div');
        div.innerHTML = cardHTML;
        evidenceGrid.appendChild(div.firstElementChild);
        safeCreateIcons();
    }
    
    function renderSimulatedResults() {
        if (!evidenceGrid) return;
        overallSummary.textContent = `Scan complete — ${selectedFiles.length} file${selectedFiles.length>1?'s':''} processed (local simulation).`;
        evidenceGrid.innerHTML = '';
        selectedFiles.forEach(file => {
            const fake = Math.random()*100;
            const card = document.createElement('div');
            card.className = 'bg-card border border-gray-800 rounded-lg p-4';
            card.innerHTML = `<div class="flex justify-between"><div class="font-bold text-white">${escapeHtml(file.name)}</div><div class="text-2xl font-orbitron ${fake>70?'text-red-500':'text-green-500'}">${Math.floor(fake)}%</div></div><div class="text-xs text-gray-400 mt-2 font-mono">SIMULATED RESULT (SERVER ERROR)</div>`;
            evidenceGrid.appendChild(card);
        });
    }

    renderFileList(); updateUIState();
});