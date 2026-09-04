// NetSage AI Frontend Controller

let casesData = [];
let selectedCaseId = null;
let conceptChart = null;
let reviewChart = null;
let severityChart = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSearch();
    initForm();
    fetchData();
});

// Tab Switching Mechanism
function initTabs() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            navButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(t => t.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${targetTab}`).classList.add('active');

            // Redraw charts if switching to overview tab
            if (targetTab === 'overview') {
                updateCharts();
            }
        });
    });
}

// Fetch Merged Results from the backend
async function fetchData() {
    try {
        const response = await fetch('/api/results');
        if (!response.ok) throw new Error('Failed to fetch diagnostic results');
        casesData = await response.json();
        
        updateMetrics();
        populateSidebar(casesData);
        updateCharts();
        populateResponsibleLog();

        // Auto-select first case if none selected
        if (casesData.length > 0 && selectedCaseId === null) {
            selectCase(casesData[0].case_id);
        } else if (selectedCaseId !== null) {
            // Keep current case selected and refresh details
            selectCase(selectedCaseId);
        }
    } catch (err) {
        console.error('Error fetching data:', err);
    }
}

// Update Top Metrics Cards
function updateMetrics() {
    document.getElementById('metric-total-cases').textContent = casesData.length;

    const reviewedCount = casesData.filter(c => c.human_review && c.human_review.status !== 'Unreviewed').length;
    document.getElementById('metric-reviewed').textContent = `${reviewedCount} / ${casesData.length}`;

    // Compute Agreement Rate: Accepted / (Accepted + Edited + Rejected)
    const accepted = casesData.filter(c => c.human_review && c.human_review.status === 'Accepted').length;
    const edited = casesData.filter(c => c.human_review && c.human_review.status === 'Edited').length;
    const rejected = casesData.filter(c => c.human_review && c.human_review.status === 'Rejected').length;
    const reviewedTotal = accepted + edited + rejected;

    const agreementValue = reviewedTotal > 0 ? ((accepted / reviewedTotal) * 100).toFixed(1) + '%' : '100%';
    document.getElementById('metric-agreement').textContent = agreementValue;

    // Rules count
    const totalRulesTriggered = casesData.reduce((acc, c) => acc + (c.rule_checks ? c.rule_checks.length : 0), 0);
    document.getElementById('metric-rules').textContent = totalRulesTriggered;
}

// Draw/Update Data Visualizations using Chart.js
function updateCharts() {
    if (casesData.length === 0) return;

    // 1. Concept / Domain Chart
    const concepts = {};
    casesData.forEach(c => {
        concepts[c.concept] = (concepts[c.concept] || 0) + 1;
    });

    const conceptCtx = document.getElementById('conceptChart').getContext('2d');
    if (conceptChart) conceptChart.destroy();
    conceptChart = new Chart(conceptCtx, {
        type: 'bar',
        data: {
            labels: Object.keys(concepts),
            datasets: [{
                label: 'Cases',
                data: Object.values(concepts),
                backgroundColor: 'rgba(139, 92, 246, 0.65)',
                borderColor: '#8b5cf6',
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
            }
        }
    });

    // 2. Review Status Chart
    const statusCounts = { Accepted: 0, Edited: 0, Rejected: 0, Unreviewed: 0 };
    casesData.forEach(c => {
        const s = c.human_review ? c.human_review.status : 'Unreviewed';
        statusCounts[s] = (statusCounts[s] || 0) + 1;
    });

    const reviewCtx = document.getElementById('reviewChart').getContext('2d');
    if (reviewChart) reviewChart.destroy();
    reviewChart = new Chart(reviewCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(statusCounts),
            datasets: [{
                data: Object.values(statusCounts),
                backgroundColor: [
                    '#10b981', // Accepted
                    '#f59e0b', // Edited
                    '#ef4444', // Rejected
                    '#475569'  // Unreviewed
                ],
                borderWidth: 2,
                borderColor: '#090d16'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Inter' } } }
            }
        }
    });

    // 3. Severity Distribution
    const severities = { High: 0, Medium: 0, Low: 0 };
    casesData.forEach(c => {
        severities[c.severity] = (severities[c.severity] || 0) + 1;
    });

    const severityCtx = document.getElementById('severityChart').getContext('2d');
    if (severityChart) severityChart.destroy();
    severityChart = new Chart(severityCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(severities),
            datasets: [{
                data: Object.values(severities),
                backgroundColor: [
                    '#ef4444', // High
                    '#f59e0b', // Medium
                    '#0ea5e9'  // Low
                ],
                borderWidth: 2,
                borderColor: '#090d16'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Inter' } } }
            }
        }
    });
}

// Populate Cases List in Sidebar
function populateSidebar(data) {
    const list = document.getElementById('case-list');
    list.innerHTML = '';

    data.forEach(c => {
        const item = document.createElement('li');
        item.className = `case-item ${c.case_id === selectedCaseId ? 'active' : ''}`;
        item.setAttribute('data-id', c.case_id);
        
        const reviewStatus = c.human_review ? c.human_review.status : 'Unreviewed';
        
        item.innerHTML = `
            <div class="case-item-header">
                <span>VLAN ${c.concept}</span>
                <span>ID: ${c.case_id}</span>
            </div>
            <div class="case-item-title" title="${c.symptom}">${c.symptom}</div>
            <div class="case-item-footer">
                <span class="sev-tag sev-${c.severity.toLowerCase()}">${c.severity}</span>
                <span class="review-status-dot">
                    <span class="status-dot dot-${reviewStatus.toLowerCase()}"></span>
                    ${reviewStatus}
                </span>
            </div>
        `;

        item.addEventListener('click', () => selectCase(c.case_id));
        list.appendChild(item);
    });
}

// Handle Search Filter
function initSearch() {
    const searchInput = document.getElementById('case-search');
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = casesData.filter(c => 
            c.symptom.toLowerCase().includes(query) || 
            c.concept.toLowerCase().includes(query) ||
            c.expected_fault.toLowerCase().includes(query)
        );
        populateSidebar(filtered);
    });
}

// Select a Case and Load Detail Panel
function selectCase(id) {
    selectedCaseId = id;
    
    // Highlight active in sidebar
    document.querySelectorAll('.case-item').forEach(item => {
        if (parseInt(item.getAttribute('data-id')) === id) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    const caseObj = casesData.find(c => c.case_id === id);
    if (!caseObj) return;

    // Toggle Empty State / Detail State
    document.getElementById('no-case-selected').classList.add('hidden');
    const content = document.getElementById('case-content');
    content.classList.remove('hidden');

    // Fill Header Info
    document.getElementById('detail-case-id').textContent = `Case #${caseObj.case_id}`;
    document.getElementById('detail-symptom').textContent = caseObj.symptom;
    document.getElementById('detail-topology').textContent = caseObj.topology_note;
    document.getElementById('detail-show-output').textContent = caseObj.show_output;
    document.getElementById('detail-osi').textContent = caseObj.osi_layer;

    const severityTag = document.getElementById('detail-severity');
    severityTag.className = `severity-badge-${caseObj.severity.toLowerCase()}`;
    severityTag.textContent = `${caseObj.severity} Severity`;

    // Fill Deterministic Checks
    const rulesContainer = document.getElementById('detail-rule-checks');
    rulesContainer.innerHTML = '';

    const checks = caseObj.rule_checks || [];
    if (checks.length === 0) {
        rulesContainer.innerHTML = `
            <div class="rule-item">
                <span class="rule-name">All Deterministic Rules Passed</span>
                <span class="rule-status-badge rule-status-passed">PASSED</span>
            </div>
        `;
    } else {
        checks.forEach(check => {
            const checkEl = document.createElement('div');
            checkEl.className = 'rule-item triggered';
            checkEl.innerHTML = `
                <div>
                    <span class="rule-name">${check.rule_name} Check</span>
                    <p class="rule-evidence">${check.evidence}</p>
                </div>
                <span class="rule-status-badge rule-status-triggered">TRIGGERED</span>
            `;
            rulesContainer.appendChild(checkEl);
        });
    }

    // Fill AI Recommendation Info
    const aiDiag = caseObj.ai_diagnosis || {};
    document.getElementById('detail-ai-root-cause').textContent = aiDiag.root_cause || "No diagnosis available.";
    document.getElementById('detail-ai-evidence').textContent = aiDiag.evidence || "No evidence snippet found.";
    document.getElementById('detail-ai-next-command').textContent = aiDiag.next_command || "show running-config";
    document.getElementById('detail-ai-fix').textContent = aiDiag.fix_steps || "N/A";

    // Fill Human Review form state
    const hr = caseObj.human_review || {};
    const reviewStatus = hr.status || 'Unreviewed';
    
    // Select Radio Button
    const radio = document.querySelector(`input[name="review-status"][value="${reviewStatus}"]`);
    if (radio) {
        radio.checked = true;
    } else {
        // Reset if unreviewed
        document.querySelectorAll('input[name="review-status"]').forEach(r => r.checked = false);
    }

    document.getElementById('reviewer-notes').value = hr.reviewer_notes || '';
    document.getElementById('corrected-fix-steps').value = hr.corrected_fix_steps || '';

    // Handle corrected box visibility
    toggleCorrectedBox(reviewStatus);
}

// Handle Form Setup & Submissions
function initForm() {
    const radios = document.querySelectorAll('input[name="review-status"]');
    radios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            toggleCorrectedBox(e.target.value);
        });
    });

    const form = document.getElementById('review-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (selectedCaseId === null) return;

        const statusInput = document.querySelector('input[name="review-status"]:checked');
        if (!statusInput) {
            alert('Please select a verification status (Accept, Correct, or Reject).');
            return;
        }

        const reviewStatus = statusInput.value;
        const notes = document.getElementById('reviewer-notes').value;
        const correctedFix = document.getElementById('corrected-fix-steps').value;

        try {
            const response = await fetch('/api/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    case_id: selectedCaseId,
                    status: reviewStatus,
                    reviewer_notes: notes,
                    corrected_fix_steps: correctedFix
                })
            });

            if (!response.ok) throw new Error('Failed to save review');
            
            // Reload database and refresh components
            await fetchData();
            alert('Review decision successfully logged!');
        } catch (err) {
            console.error('Error submitting review:', err);
            alert('Error logging review: ' + err.message);
        }
    });
}

function toggleCorrectedBox(status) {
    const correctedGroup = document.getElementById('corrected-steps-group');
    if (status === 'Edited' || status === 'Rejected') {
        correctedGroup.classList.remove('hidden');
        // If empty, auto-copy the AI's fix as a template to edit
        const correctedArea = document.getElementById('corrected-fix-steps');
        if (!correctedArea.value) {
            correctedArea.value = document.getElementById('detail-ai-fix').textContent;
        }
    } else {
        correctedGroup.classList.add('hidden');
    }
}

// Populate TAB 3: Responsible AI Log
function populateResponsibleLog() {
    const list = document.getElementById('corrections-list');
    list.innerHTML = '';

    // Filter cases that are edited or rejected
    const corrections = casesData.filter(c => c.human_review && (c.human_review.status === 'Edited' || c.human_review.status === 'Rejected'));

    if (corrections.length === 0) {
        list.innerHTML = `
            <div class="no-corrections">
                <p>No model corrections logged yet. Use the Diagnostics Explorer to modify or reject AI recommendations.</p>
            </div>
        `;
        return;
    }

    corrections.forEach(c => {
        const card = document.createElement('div');
        card.className = 'correction-card';
        
        const aiDiag = c.ai_diagnosis || {};
        const hr = c.human_review || {};
        const statusClass = hr.status.toLowerCase();

        card.innerHTML = `
            <div class="correction-card-header ${statusClass}">
                <div>
                    <span class="correction-badge">${hr.status}</span>
                    <span class="correction-title" style="margin-left: 10px;"><strong>Case #${c.case_id}:</strong> ${c.symptom}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    OSI Layer: ${c.osi_layer} | Domain: ${c.concept}
                </div>
            </div>
            
            <div class="correction-notes">
                <span class="notes-label">Reviewer's Explanation Notes</span>
                <p>${hr.reviewer_notes || 'No review comments provided.'}</p>
            </div>

            <div class="comparison-box">
                <div class="comp-panel ai-comp">
                    <h5>Original AI Recommendation</h5>
                    <div class="comp-text"><strong>Root Cause:</strong> ${aiDiag.root_cause || 'N/A'}</div>
                    <pre class="comp-code">${aiDiag.fix_steps || 'N/A'}</pre>
                </div>
                <div class="comp-panel human-comp">
                    <h5>Corrected Human Verdict</h5>
                    <div class="comp-text"><strong>Root Cause Corrected:</strong> ${c.expected_fault}</div>
                    <pre class="comp-code">${hr.corrected_fix_steps || 'No custom configuration required.'}</pre>
                </div>
            </div>
        `;
        list.appendChild(card);
    });
}
