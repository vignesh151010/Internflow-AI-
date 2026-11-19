/**
 * InternFlow AI - Admin Portal Logic
 */

let currentExcelPreviewData = null;
let currentSelectedInternId = null;
let currentEvaluatingSubmissionId = null;
let currentAiReportData = null;

// Initialize Admin Portal
window.addEventListener('DOMContentLoaded', async () => {
  const user = api.getUser();
  const token = api.getToken();

  if (!token || !user || user.role !== 'admin') {
    api.clearAuth();
    window.location.href = '/';
    return;
  }

  document.getElementById('admin-user-name').innerText = user.name || 'Administrator';
  document.getElementById('admin-avatar').innerText = (user.name || 'AD').substring(0, 2).toUpperCase();

  await checkAdminOllama();
  await loadDashboard();
  await loadInternsDropdown();
  await checkGoogleOAuthStatus();
  await checkSmtpStatus();

  // Setup drag and drop for Excel
  setupDropzone();
});

function handleLogout() {
  api.clearAuth();
  window.location.href = '/';
}

function showAdminSection(sectionName) {
  document.querySelectorAll('.admin-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const target = document.getElementById(`section-${sectionName}`);
  if (target) {
    target.style.display = 'block';
  }

  const navItems = Array.from(document.querySelectorAll('.nav-item'));
  const activeNav = navItems.find(item => item.getAttribute('onclick')?.includes(sectionName));
  if (activeNav) activeNav.classList.add('active');

  const titles = {
    dashboard: 'Overview & Platform Statistics',
    excel: 'Excel Import & Validation Pipeline',
    interns: 'Enrolled Intern Directory',
    roadmaps: 'AI Roadmaps & Curriculum Milestones',
    submissions: 'Task Submissions & AI Review Queue',
    email: 'Gmail SMTP System & Delivery Queue',
    meetings: 'Scheduled Review Syncs & Google Meet',
    attendance: 'Daily Intern Attendance Tracker',
    monitoring: 'Enterprise Integration Health Probes',
    ollama: 'Ollama Local AI Control Center',
    audit: 'System Audit Logs & Operations Trail',
    automation: 'Automated Lifecycle Control Center',
    certificates: 'Verified Completion Certificates & QR'
  };
  document.getElementById('section-title').innerText = titles[sectionName] || 'Admin Portal';

  // Section triggers
  if (sectionName === 'dashboard') loadDashboard();
  else if (sectionName === 'interns') loadInterns();
  else if (sectionName === 'submissions') loadSubmissions();
  else if (sectionName === 'email') loadEmailLogs();
  else if (sectionName === 'meetings') loadMeetings();
  else if (sectionName === 'attendance') loadAdminAttendance();
  else if (sectionName === 'monitoring') loadIntegrationsStatus();
  else if (sectionName === 'audit') loadAuditLogs();
  else if (sectionName === 'roadmaps') loadInternsDropdown();
  else if (sectionName === 'automation') {
    loadAutomationOverview();
    loadAutomationJobs();
    loadAtRiskInterns();
    loadAutomationScheduleConfig();
  }
  else if (sectionName === 'certificates') loadCertificatesRoster();
}

async function checkAdminOllama(manual = false) {
  const pill = document.getElementById('admin-ollama-pill');
  const text = document.getElementById('admin-ollama-text');
  const diagStatus = document.getElementById('ollama-diag-status');
  const diagModels = document.getElementById('ollama-diag-models');
  const diagEngine = document.getElementById('ollama-diag-engine');

  try {
    const status = await api.get('/ollama/status');
    if (status.connected) {
      pill.className = 'ai-pill online';
      text.innerText = `Ollama (${status.available_models.length} Models)`;
      if (diagStatus) diagStatus.innerHTML = `<span style="color: var(--success);">Connected & Active</span>`;
      if (diagModels) diagModels.innerText = status.available_models.join(', ') || 'No models pulled';
      if (diagEngine) diagEngine.innerText = `Ollama LLM (${status.active_model || 'Local'})`;
    } else {
      pill.className = 'ai-pill offline';
      text.innerText = 'Local Fallback Engine';
      if (diagStatus) diagStatus.innerHTML = `<span style="color: var(--warning);">Offline (Autonomous Local AI Active)</span>`;
      if (diagModels) diagModels.innerText = 'Local Domain Knowledge Engine';
      if (diagEngine) diagEngine.innerText = 'Domain Curriculum Engine';
    }
    if (manual) showToast(status.status_text, status.connected ? 'success' : 'info');
  } catch (err) {
    pill.className = 'ai-pill offline';
    text.innerText = 'Autonomous Local AI';
  }
}

// 1. DASHBOARD OVERVIEW
async function loadDashboard() {
  try {
    const stats = await api.get('/admin/dashboard');

    document.getElementById('stat-total-interns').innerText = stats.total_interns;
    document.getElementById('stat-active-interns').innerText = stats.active_interns;
    document.getElementById('stat-completed-interns').innerText = stats.completed_interns;
    document.getElementById('stat-pending-reviews').innerText = stats.pending_reviews;
    document.getElementById('stat-avg-score').innerText = stats.average_performance_score;
    document.getElementById('stat-completion-rate').innerText = `${stats.internship_completion_rate}%`;
    document.getElementById('stat-completion-bar').style.width = `${stats.internship_completion_rate}%`;

    const domainList = document.getElementById('domain-distribution-list');
    domainList.innerHTML = '';
    const domains = Object.entries(stats.domain_distribution);
    if (domains.length === 0) {
      domainList.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No interns enrolled yet. Upload an Excel spreadsheet to begin.</p>';
    } else {
      domains.forEach(([domain, count]) => {
        const percent = Math.round((count / (stats.total_interns || 1)) * 100);
        domainList.innerHTML += `
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; margin-bottom: 4px;">
              <span>${domain}</span>
              <span>${count} (${percent}%)</span>
            </div>
            <div class="progress-bar-bg" style="height: 6px;">
              <div class="progress-bar-fill" style="width: ${percent}%;"></div>
            </div>
          </div>
        `;
      });
    }

    const activityBody = document.getElementById('dashboard-activity-body');
    activityBody.innerHTML = '';
    if (!stats.recent_activities || stats.recent_activities.length === 0) {
      activityBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No activity recorded yet.</td></tr>';
    } else {
      stats.recent_activities.forEach(act => {
        activityBody.innerHTML += `
          <tr>
            <td style="font-size: 12px; color: var(--text-muted);">${act.timestamp}</td>
            <td><span class="badge badge-submitted">${act.action}</span></td>
            <td><strong>${act.entity}</strong></td>
            <td style="font-size: 12.5px;">${act.details}</td>
          </tr>
        `;
      });
    }
  } catch (err) {
    showToast(`Failed to load stats: ${err.message}`, 'error');
  }
}

// 2. EXCEL UPLOAD & PREVIEW SYSTEM
function setupDropzone() {
  const dropzone = document.getElementById('excel-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleExcelFileSelect(files[0]);
    }
  });
}

async function handleExcelFileSelect(file) {
  if (!file) return;
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
    showToast('Please select an Excel (.xlsx or .xls) file.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  showToast(`Parsing ${file.name}...`, 'info');

  try {
    const res = await api.upload('/excel/upload', formData);
    currentExcelPreviewData = res;
    renderExcelPreview(res);
    showToast(`Parsed ${res.total_rows} rows: ${res.valid_rows_count} valid, ${res.invalid_rows_count} errors.`, 'success');
  } catch (err) {
    showToast(`Excel upload failed: ${err.message}`, 'error');
  }
}

function renderExcelPreview(preview) {
  const summaryBox = document.getElementById('excel-summary-box');
  const container = document.getElementById('excel-preview-container');
  const tbody = document.getElementById('excel-preview-body');

  summaryBox.style.display = 'block';
  container.style.display = 'block';

  document.getElementById('excel-summary-title').innerText = `File: ${preview.filename} (${preview.total_rows} Rows)`;
  document.getElementById('excel-summary-desc').innerText = preview.summary_message;

  tbody.innerHTML = '';
  preview.rows.forEach((row, idx) => {
    const tr = document.createElement('tr');
    if (!row.is_valid) {
      tr.className = 'row-invalid';
    }

    let validationBadge = row.is_valid 
      ? '<span class="badge badge-approved">✓ Valid</span>' 
      : '<span class="badge badge-rejected">✕ Action Required</span>';

    let errorHtml = '';
    if (row.errors && row.errors.length > 0) {
      errorHtml = row.errors.map(err => `<div class="badge-error">${err}</div>`).join('');
    }
    if (row.warnings && row.warnings.length > 0) {
      errorHtml += row.warnings.map(w => `<div class="badge badge-pending">${w}</div>`).join('');
    }

    tr.innerHTML = `
      <td style="font-weight: 600;">${row.row_index}</td>
      <td>${validationBadge} ${errorHtml}</td>
      <td><input class="editable-cell" data-idx="${idx}" data-field="name" value="${row.name}"></td>
      <td><input class="editable-cell" data-idx="${idx}" data-field="email" value="${row.email}"></td>
      <td><input class="editable-cell" data-idx="${idx}" data-field="domain" value="${row.domain}"></td>
      <td><input class="editable-cell" data-idx="${idx}" data-field="main_task" value="${row.main_task}"></td>
      <td><input class="editable-cell" data-idx="${idx}" data-field="task_description" value="${row.task_description || ''}"></td>
      <td><input class="editable-cell" type="date" data-idx="${idx}" data-field="start_date" value="${row.start_date}"></td>
      <td><input class="editable-cell" type="number" min="1" max="52" data-idx="${idx}" data-field="duration_weeks" value="${row.duration_weeks}" style="width: 60px;"></td>
      <td><input class="editable-cell" type="date" data-idx="${idx}" data-field="end_date" value="${row.end_date}"></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('.editable-cell').forEach(input => {
    input.addEventListener('change', (e) => {
      const idx = parseInt(e.target.dataset.idx);
      const field = e.target.dataset.field;
      currentExcelPreviewData.rows[idx][field] = e.target.value;
    });
  });
}

async function approveExcelImport() {
  if (!currentExcelPreviewData || !currentExcelPreviewData.rows || currentExcelPreviewData.rows.length === 0) {
    showToast('No Excel data available to approve.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-approve-import');
  const autoRoadmaps = document.getElementById('auto-generate-roadmaps-toggle').checked;

  const approvedRows = currentExcelPreviewData.rows.map(r => ({
    row_index: r.row_index,
    name: r.name,
    email: r.email,
    domain: r.domain,
    main_task: r.main_task,
    task_description: r.task_description || '',
    start_date: r.start_date,
    duration_weeks: parseInt(r.duration_weeks) || 4,
    end_date: r.end_date
  }));

  btn.disabled = true;
  btn.innerText = 'Creating Accounts & AI Roadmaps...';

  try {
    const res = await api.post('/excel/approve', {
      approved_rows: approvedRows,
      generate_roadmaps_automatically: autoRoadmaps
    });

    showToast(res.message, 'success', 6000);
    document.getElementById('excel-summary-box').style.display = 'none';
    document.getElementById('excel-preview-container').style.display = 'none';
    currentExcelPreviewData = null;

    await loadDashboard();
    await loadInternsDropdown();
    showAdminSection('interns');
  } catch (err) {
    showToast(`Approval failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Approve & Import Valid Rows';
  }
}

// 3. INTERN MANAGEMENT
async function loadInterns() {
  const search = document.getElementById('intern-search')?.value || '';
  const domain = document.getElementById('intern-domain-filter')?.value || '';

  try {
    let url = `/admin/interns?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (domain) url += `domain=${encodeURIComponent(domain)}&`;

    const interns = await api.get(url);
    const tbody = document.getElementById('interns-table-body');
    tbody.innerHTML = '';

    if (interns.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: var(--text-muted);">No interns found matching filter.</td></tr>';
      return;
    }

    interns.forEach(i => {
      tbody.innerHTML += `
        <tr>
          <td><strong style="color: var(--primary);">${i.intern_code}</strong></td>
          <td>
            <div style="font-weight: 600;">${i.name}</div>
            ${i.invitation_token ? `<div style="font-size: 10px; color: var(--accent);">Invite Token: ${i.invitation_token.substring(0, 8)}...</div>` : ''}
          </td>
          <td style="font-size: 12.5px;">${i.email}</td>
          <td><span class="badge badge-submitted">${i.domain}</span></td>
          <td style="max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${i.main_task}">
            ${i.main_task}
          </td>
          <td>${i.duration_weeks} Weeks</td>
          <td style="min-width: 130px;">
            <div style="font-size: 11px; margin-bottom: 2px;">${i.completed_tasks_count} of ${i.tasks_count} Milestones (${i.progress_percentage}%)</div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${i.progress_percentage}%;"></div>
            </div>
          </td>
          <td style="font-weight: 700;">${i.total_score > 0 ? i.total_score : '-'}</td>
          <td><span class="badge badge-${i.status}">${i.status}</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="viewInternRoadmap(${i.id})">Roadmap</button>
              <button class="btn btn-secondary btn-sm" onclick="deleteIntern(${i.id})" title="Delete" style="color: var(--danger);">✕</button>
            </div>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load interns: ${err.message}`, 'error');
  }
}

async function deleteIntern(internId) {
  if (!confirm('Are you sure you want to delete this intern and all their associated records?')) return;
  try {
    await api.delete(`/admin/interns/${internId}`);
    showToast('Intern removed successfully.', 'success');
    loadInterns();
    loadDashboard();
    loadInternsDropdown();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'error');
  }
}

// 4. ROADMAPS SECTION
async function loadInternsDropdown() {
  const select = document.getElementById('roadmap-intern-select');
  const filter = document.getElementById('intern-domain-filter');
  if (!select) return;

  try {
    const interns = await api.get('/admin/interns');
    select.innerHTML = '<option value="">Choose an intern...</option>';
    
    const domainSet = new Set();
    interns.forEach(i => {
      select.innerHTML += `<option value="${i.id}">${i.intern_code} - ${i.name} (${i.domain})</option>`;
      domainSet.add(i.domain);
    });

    if (filter) {
      filter.innerHTML = '<option value="">All Domains</option>';
      domainSet.forEach(d => {
        filter.innerHTML += `<option value="${d}">${d}</option>`;
      });
    }
  } catch (err) {
    console.error('Failed to populate interns dropdown:', err);
  }
}

function viewInternRoadmap(internId) {
  showAdminSection('roadmaps');
  const select = document.getElementById('roadmap-intern-select');
  if (select) {
    select.value = internId;
    loadInternRoadmap(internId);
  }
}

async function loadInternRoadmap(internId) {
  if (!internId) {
    document.getElementById('roadmap-intern-banner').style.display = 'none';
    document.getElementById('roadmaps-list-container').innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 40px 0;">Select an intern above.</p>';
    currentSelectedInternId = null;
    return;
  }

  currentSelectedInternId = internId;
  const container = document.getElementById('roadmaps-list-container');
  container.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 20px 0;">Loading AI roadmap...</p>';

  try {
    const intern = await api.get(`/admin/interns/${internId}`);
    
    const banner = document.getElementById('roadmap-intern-banner');
    banner.style.display = 'block';
    document.getElementById('roadmap-banner-name').innerText = `${intern.name} (${intern.intern_code})`;
    document.getElementById('roadmap-banner-project').innerText = `Main Project: ${intern.main_task} — ${intern.task_description || ''}`;
    document.getElementById('roadmap-banner-domain').innerText = intern.domain;

    container.innerHTML = '';
    if (!intern.roadmaps || intern.roadmaps.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
          <p style="color: var(--text-muted); margin-bottom: 16px;">No roadmap milestones generated for this intern yet.</p>
          <button class="btn btn-primary" onclick="triggerRegenerateRoadmap()">Generate AI Roadmap Now</button>
        </div>
      `;
      return;
    }

    intern.roadmaps.forEach(r => {
      const weekCard = document.createElement('div');
      weekCard.className = 'week-card open';

      let tasksHtml = '';
      r.tasks.forEach(t => {
        let subInfo = '<span class="badge badge-pending">Pending Submission</span>';
        if (t.latest_submission) {
          subInfo = `<span class="badge badge-${t.latest_submission.status}">${t.latest_submission.status.toUpperCase()}</span>`;
          if (t.latest_submission.submission_link) {
            subInfo += ` <a href="${t.latest_submission.submission_link}" target="_blank" style="margin-left: 8px; font-size: 12px; color: var(--secondary);">View Work ↗</a>`;
          }
        }

        tasksHtml += `
          <div style="background: #F8FAFC; border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 16px; margin-top: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <h5 style="font-size: 14px; font-weight: 700; color: var(--primary);">${t.title}</h5>
              <div>${subInfo}</div>
            </div>
            <p style="font-size: 13px; color: var(--text-main); margin-bottom: 12px;">${t.description}</p>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px;">
              <div style="background: white; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
                <strong>Step-by-Step Instructions:</strong>
                <div style="white-space: pre-line; margin-top: 4px; color: #475569;">${t.instructions || 'N/A'}</div>
              </div>
              <div style="background: white; padding: 10px; border-radius: 4px; border: 1px solid var(--border-color);">
                <strong>Recommended Tech Stack:</strong>
                <div style="margin-top: 4px; color: var(--secondary); font-weight: 600;">${t.technologies || 'N/A'}</div>
                <strong style="display: block; margin-top: 8px;">Expected Output:</strong>
                <div style="margin-top: 4px; color: #475569;">${t.expected_output || 'N/A'}</div>
              </div>
            </div>

            <div style="margin-top: 10px; font-size: 11.5px; color: var(--text-muted); display: flex; justify-content: space-between;">
              <span><strong>Evaluation Criteria:</strong> ${t.evaluation_criteria || 'Quality and test coverage'}</span>
              <span><strong>Deadline:</strong> ${t.deadline ? new Date(t.deadline).toLocaleDateString() : 'N/A'}</span>
            </div>
          </div>
        `;
      });

      weekCard.innerHTML = `
        <div class="week-card-header" onclick="this.parentElement.classList.toggle('open')">
          <div>
            <span style="font-weight: 700; color: var(--primary);">Week ${r.week_number}:</span>
            <span style="font-weight: 600; margin-left: 6px;">${r.title}</span>
            <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">(${r.theme || ''})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="badge badge-${r.status}">${r.status.toUpperCase()}</span>
            <span style="font-size: 12px; color: var(--text-muted);">${r.estimated_hours}h estimated</span>
          </div>
        </div>
        <div class="week-card-body">
          <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
            <strong>Weekly Objectives:</strong> ${r.objectives || ''}
          </div>
          ${tasksHtml}
        </div>
      `;
      container.appendChild(weekCard);
    });
  } catch (err) {
    showToast(`Failed to load roadmap: ${err.message}`, 'error');
  }
}

async function triggerRegenerateRoadmap() {
  if (!currentSelectedInternId) {
    showToast('Please select an intern first.', 'warning');
    return;
  }
  showToast('AI is synthesizing customized roadmap...', 'info');
  try {
    const res = await api.post('/roadmaps/generate', {
      intern_id: currentSelectedInternId,
      force_regenerate: true
    });
    showToast(res.message, 'success');
    loadInternRoadmap(currentSelectedInternId);
  } catch (err) {
    showToast(`Generation failed: ${err.message}`, 'error');
  }
}

// 5. SUBMISSIONS & AI EVALUATION SYSTEM
async function loadSubmissions() {
  const statusFilter = document.getElementById('submission-status-filter')?.value;
  try {
    let url = '/admin/submissions';
    if (statusFilter) url += `?status=${statusFilter}`;
    const submissions = await api.get(url);
    const tbody = document.getElementById('submissions-table-body');
    tbody.innerHTML = '';

    if (submissions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No submissions found.</td></tr>';
      return;
    }

    submissions.forEach(s => {
      let scoreBadge = s.evaluation ? `<strong style="color: var(--primary);">${s.evaluation.score}/100</strong>` : '<span style="color: var(--text-muted);">Unscored</span>';
      
      let filesHtml = '';
      if (s.file_path) {
        filesHtml += `<span class="badge badge-submitted">${s.file_type || 'File'}</span> `;
      }
      if (s.submission_link) {
        filesHtml += `<a href="${s.submission_link}" target="_blank" style="color: var(--secondary); font-weight: 600;">Link ↗</a>`;
      }
      if (s.version > 1) {
        filesHtml += ` <span class="badge badge-pending">v${s.version}</span>`;
      }
      if (!filesHtml) filesHtml = 'Notes only';

      tbody.innerHTML += `
        <tr>
          <td style="font-size: 12px; color: var(--text-muted);">${new Date(s.submitted_at).toLocaleString()}</td>
          <td>
            <div style="font-weight: 600;">${s.intern_name}</div>
            <div style="font-size: 11px; color: var(--text-muted);">${s.intern_email}</div>
          </td>
          <td><span class="badge badge-submitted">${s.domain}</span></td>
          <td>
            <div style="font-weight: 600;">${s.task_title}</div>
            <div style="font-size: 11px; color: var(--text-muted);">Week ${s.week_number}</div>
          </td>
          <td>${filesHtml}</td>
          <td><span class="badge badge-${s.status}">${s.status.toUpperCase()}</span></td>
          <td>${scoreBadge}</td>
          <td>
            <button class="btn btn-primary btn-sm" onclick='openEvaluationModal(${JSON.stringify(s)})'>
              ${s.evaluation ? 'Review & Re-Evaluate' : 'AI Evaluate'}
            </button>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load submissions: ${err.message}`, 'error');
  }
}

function openEvaluationModal(submission) {
  currentEvaluatingSubmissionId = submission.id;
  document.getElementById('eval-submission-id').value = submission.id;
  document.getElementById('eval-modal-intern-task').innerText = `${submission.intern_name} — ${submission.task_title} (Week ${submission.week_number}, Version ${submission.version || 1})`;
  
  let linkStr = submission.submission_link 
    ? `Deliverable URL: <a href="${submission.submission_link}" target="_blank">${submission.submission_link}</a>` 
    : 'No URL provided';
  if (submission.file_path) {
    linkStr += ` | Attached: ${submission.file_path.split('\\').pop()}`;
  }
  document.getElementById('eval-modal-sub-link').innerHTML = linkStr;
  document.getElementById('eval-modal-notes').innerText = submission.notes ? `Intern Implementation Notes: "${submission.notes}"` : '';

  // Clear previous AI rubric tags
  document.getElementById('eval-tags-fulfilled').innerHTML = '<span style="color: var(--text-muted);">Click "Run Ollama AI Evaluation" to generate structured rubric breakdown.</span>';
  document.getElementById('eval-tags-missing').innerHTML = '<span style="color: var(--text-muted);">-</span>';

  if (submission.evaluation) {
    document.getElementById('eval-score').value = submission.evaluation.score;
    document.getElementById('eval-feedback').value = submission.evaluation.feedback;
    document.getElementById('eval-strengths').value = submission.evaluation.strengths || '';
    document.getElementById('eval-improvements').value = submission.evaluation.improvements || '';
    document.getElementById('eval-final-status').value = submission.evaluation.final_status || 'approved';
  } else {
    document.getElementById('eval-score').value = '85';
    document.getElementById('eval-feedback').value = '';
    document.getElementById('eval-strengths').value = '';
    document.getElementById('eval-improvements').value = '';
    document.getElementById('eval-final-status').value = 'approved';
  }

  openModal('evaluation-modal');
}

async function triggerAiEvaluation() {
  if (!currentEvaluatingSubmissionId) return;
  const btn = document.getElementById('btn-run-ai-eval');
  btn.disabled = true;
  btn.innerText = 'Evaluating with Ollama AI...';

  try {
    const res = await api.post(`/admin/submissions/${currentEvaluatingSubmissionId}/ai-evaluate`, {});
    const r = res.report;
    currentAiReportData = r;

    document.getElementById('eval-score').value = r.score;
    document.getElementById('eval-feedback').value = r.feedback_summary || '';
    document.getElementById('eval-strengths').value = r.strengths_summary || '';
    document.getElementById('eval-improvements').value = (r.step_by_step_corrections || []).join('\n');
    document.getElementById('eval-final-status').value = r.final_status || 'approved';

    // Populate tags
    const fulfilledDiv = document.getElementById('eval-tags-fulfilled');
    fulfilledDiv.innerHTML = '';
    (r.requirements_fulfilled || []).forEach(item => {
      fulfilledDiv.innerHTML += `<div class="tag-item success">✓ ${item}</div>`;
    });

    const missingDiv = document.getElementById('eval-tags-missing');
    missingDiv.innerHTML = '';
    if (!r.missing_requirements || r.missing_requirements.length === 0) {
      missingDiv.innerHTML = '<div class="tag-item success">None (All requirements met)</div>';
    } else {
      r.missing_requirements.forEach(item => {
        missingDiv.innerHTML += `<div class="tag-item danger">✕ ${item}</div>`;
      });
    }

    showToast(`Ollama Evaluation Complete! Proposed score: ${r.score}/100`, 'success');
  } catch (err) {
    showToast(`AI evaluation probe failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = '✨ Run Ollama AI Evaluation';
  }
}

async function handleEvaluationSubmit(e) {
  e.preventDefault();
  const subId = document.getElementById('eval-submission-id').value;
  const score = parseFloat(document.getElementById('eval-score').value);
  const finalStatus = document.getElementById('eval-final-status').value;
  const feedback = document.getElementById('eval-feedback').value;
  const strengths = document.getElementById('eval-strengths').value;
  const improvements = document.getElementById('eval-improvements').value;

  const btn = document.getElementById('btn-submit-eval');
  btn.disabled = true;
  btn.innerText = 'Publishing & Dispatching Email...';

  const payload = {
    score: score,
    completion_percentage: score,
    final_status: finalStatus,
    feedback_summary: feedback,
    strengths_summary: strengths,
    improvement_suggestions: improvements ? improvements.split('\n') : [],
    step_by_step_corrections: improvements ? improvements.split('\n') : [],
    requirements_fulfilled: currentAiReportData ? currentAiReportData.requirements_fulfilled : [],
    missing_requirements: currentAiReportData ? currentAiReportData.missing_requirements : []
  };

  try {
    const res = await api.post(`/admin/submissions/${subId}/publish-evaluation`, payload);
    showToast(res.message, 'success', 5000);
    closeModal('evaluation-modal');
    loadSubmissions();
    loadDashboard();
  } catch (err) {
    showToast(`Failed to publish evaluation: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Publish Evaluation & Dispatch Email';
  }
}

// 6. GMAIL SMTP & EMAIL QUEUE
async function checkSmtpStatus() {
  try {
    const s = await api.get('/email/status');
    const hostEl = document.getElementById('smtp-host-text');
    const emailEl = document.getElementById('smtp-email-text');
    if (hostEl) hostEl.innerText = `${s.server}:${s.port}`;
    if (emailEl) emailEl.innerText = s.sender_email;
  } catch (e) {}
}

async function testSmtpConnection() {
  showToast('Testing SSL/TLS handshake with SMTP server...', 'info');
  try {
    const res = await api.post('/email/test-connection', {});
    const badge = document.getElementById('smtp-handshake-badge');
    if (res.success) {
      if (badge) {
        badge.className = 'badge badge-approved';
        badge.innerText = 'Handshake & Auth OK';
      }
      showToast(res.message, 'success');
    } else {
      if (badge) {
        badge.className = 'badge badge-rejected';
        badge.innerText = 'Setup Required';
      }
      showToast(res.message, 'warning', 6000);
    }
  } catch (err) {
    showToast(`SMTP test error: ${err.message}`, 'error');
  }
}

async function loadEmailLogs() {
  const statusFilter = document.getElementById('email-log-status-filter')?.value;
  try {
    let url = '/email/logs';
    if (statusFilter) url += `?status=${statusFilter}`;
    const logs = await api.get(url);
    const tbody = document.getElementById('email-logs-tbody');
    tbody.innerHTML = '';

    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No emails dispatched yet.</td></tr>';
      return;
    }

    logs.forEach(l => {
      let statusBadge = '';
      let retryBtn = '';

      if (l.status === 'SMTP_ACCEPTED') {
        statusBadge = '<span class="badge badge-approved">SMTP_ACCEPTED</span>';
      } else if (l.status === 'FAILED') {
        statusBadge = '<span class="badge badge-rejected" title="' + (l.error_message || '') + '">FAILED</span>';
        retryBtn = `<button class="btn btn-secondary btn-sm" onclick="retryEmail(${l.id})">Retry</button>`;
      } else {
        statusBadge = '<span class="badge badge-pending">QUEUED</span>';
      }

      tbody.innerHTML += `
        <tr>
          <td style="font-size: 12px; color: var(--text-muted);">${new Date(l.sent_at).toLocaleString()}</td>
          <td style="font-weight: 600;">${l.recipient_email}</td>
          <td>${l.subject}</td>
          <td><span class="badge badge-submitted">${l.email_type}</span></td>
          <td>${statusBadge}</td>
          <td>${l.retry_count || 0}</td>
          <td>${retryBtn}</td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load email logs: ${err.message}`, 'error');
  }
}

async function handleSendTestEmail(e) {
  e.preventDefault();
  const recipient = document.getElementById('test-email-recipient').value;
  const template = document.getElementById('test-email-template').value;
  const btn = document.getElementById('btn-dispatch-test-email');

  btn.disabled = true;
  btn.innerText = 'Dispatching...';

  try {
    const res = await api.post('/email/send-test', {
      recipient_email: recipient,
      template_type: template
    });
    showToast(`Status: ${res.status}. ${res.message || res.error || ''}`, res.status === 'SMTP_ACCEPTED' ? 'success' : 'info');
    closeModal('send-test-email-modal');
    loadEmailLogs();
  } catch (err) {
    showToast(`Dispatch failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Dispatch Email via SMTP';
  }
}

async function retryEmail(logId) {
  showToast(`Retrying email #${logId}...`, 'info');
  try {
    const res = await api.post(`/email/retry/${logId}`, {});
    showToast(res.message, res.success ? 'success' : 'error');
    loadEmailLogs();
  } catch (err) {
    showToast(`Retry error: ${err.message}`, 'error');
  }
}

// 7. GOOGLE CALENDAR & MEET INTEGRATION
async function checkGoogleOAuthStatus() {
  try {
    const s = await api.get('/google/status');
    const line = document.getElementById('google-oauth-status-line');
    const btn = document.getElementById('btn-auth-google');

    if (line) {
      if (s.authorized) {
        line.innerHTML = `<span style="color: var(--success); font-weight: 700;">✓ Google OAuth: Authorized (Genuine Google Meet Generation Active)</span>`;
        if (btn) btn.innerText = 'Re-Authorize Google';
      } else if (s.configured) {
        line.innerHTML = `<span style="color: var(--warning); font-weight: 600;">⚠ Google Credentials Present — Click Authorize</span>`;
      } else {
        line.innerHTML = `<span style="color: var(--text-muted);">Google OAuth: Setup Required (client_id in .env)</span>`;
      }
    }
  } catch (e) {}
}

async function authorizeGoogleCalendar() {
  try {
    const res = await api.get('/google/auth-url');
    if (res.auth_url) {
      window.open(res.auth_url, '_blank');
      showToast('Opening Google OAuth authorization page...', 'info');
    }
  } catch (err) {
    showToast(`Google OAuth configuration required in .env: ${err.message}`, 'warning');
  }
}

async function loadMeetings() {
  try {
    const meetings = await api.get('/admin/meetings');
    const tbody = document.getElementById('meetings-table-body');
    tbody.innerHTML = '';
    if (meetings.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No meetings scheduled.</td></tr>';
      return;
    }

    meetings.forEach(m => {
      let meetLink = m.google_meet_url || m.meeting_link;
      let meetHtml = meetLink ? `<a href="${meetLink}" target="_blank" style="color: var(--secondary); font-weight: 600;">Join Meet ↗</a>` : '-';
      let syncBadge = m.is_google_calendar_synced 
        ? '<span class="badge badge-approved">✓ Google Synced</span>' 
        : '<span class="badge badge-pending">Local Only</span>';

      tbody.innerHTML += `
        <tr>
          <td style="font-weight: 600;">${m.title}</td>
          <td><span class="badge badge-submitted">${m.meeting_type}</span></td>
          <td>${new Date(m.scheduled_time).toLocaleString()}</td>
          <td>${meetHtml}</td>
          <td>${syncBadge}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="syncMeetingGoogle(${m.id})">Sync Calendar</button>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load meetings: ${err.message}`, 'error');
  }
}

async function handleScheduleMeeting(e) {
  e.preventDefault();
  const title = document.getElementById('meeting-title').value;
  const meeting_type = document.getElementById('meeting-type').value;
  const scheduled_time = document.getElementById('meeting-time').value;
  const duration_minutes = parseInt(document.getElementById('meeting-duration').value);
  const syncGoogle = document.getElementById('meeting-sync-google').checked;

  try {
    const meeting = await api.post('/admin/meetings', {
      title,
      meeting_type,
      scheduled_time,
      duration_minutes,
      intern_ids: 'all'
    });

    if (syncGoogle) {
      await api.post(`/google/meetings/${meeting.id}/sync-calendar`, {});
    }

    showToast('Meeting scheduled successfully.', 'success');
    document.getElementById('meeting-title').value = '';
    loadMeetings();
  } catch (err) {
    showToast(`Scheduling failed: ${err.message}`, 'error');
  }
}

async function syncMeetingGoogle(meetingId) {
  showToast('Syncing with Google Calendar...', 'info');
  try {
    const res = await api.post(`/google/meetings/${meetingId}/sync-calendar`, {});
    if (res.success) {
      showToast('Meeting synced! Genuine Google Meet generated and invites dispatched.', 'success');
    } else {
      showToast(res.details || res.error || 'Google Calendar authorization required.', 'warning');
    }
    loadMeetings();
  } catch (err) {
    showToast(`Google sync failed: ${err.message}`, 'error');
  }
}

// 8. ATTENDANCE TRACKING
async function loadAdminAttendance() {
  const dateFilter = document.getElementById('attendance-date-filter')?.value;
  try {
    let url = '/admin/attendance';
    if (dateFilter) url += `?date=${dateFilter}`;
    const records = await api.get(url);
    const tbody = document.getElementById('admin-attendance-tbody');
    tbody.innerHTML = '';

    if (records.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No attendance records found.</td></tr>';
      return;
    }

    records.forEach(r => {
      let statusBadge = r.status === 'present' ? '<span class="badge badge-approved">Present</span>' : '<span class="badge badge-rejected">Absent</span>';
      tbody.innerHTML += `
        <tr>
          <td>${r.date}</td>
          <td><strong>${r.intern_code}</strong></td>
          <td>${r.intern_name}</td>
          <td>${statusBadge}</td>
          <td>${r.notes || '-'}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="toggleAttendance(${r.intern_id}, '${r.status === 'present' ? 'absent' : 'present'}')">Toggle</button>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load attendance: ${err.message}`, 'error');
  }
}

async function toggleAttendance(internId, newStatus) {
  try {
    await api.post('/admin/attendance/mark', {
      intern_id: internId,
      status: newStatus,
      notes: `Updated by Admin to ${newStatus}`
    });
    showToast(`Attendance updated to ${newStatus}.`, 'success');
    loadAdminAttendance();
  } catch (err) {
    showToast(`Update failed: ${err.message}`, 'error');
  }
}

// 9. INTEGRATION HEALTH MONITORING
async function loadIntegrationsStatus() {
  try {
    const s = await api.get('/admin/integrations/status');

    // SMTP
    const smtpBadge = document.getElementById('probe-smtp-badge');
    if (smtpBadge) {
      smtpBadge.className = s.smtp.configured ? 'badge badge-approved' : 'badge badge-pending';
      smtpBadge.innerText = s.smtp.configured ? 'Active' : 'Unset';
    }
    document.getElementById('probe-smtp-desc').innerText = s.smtp.status_text;
    document.getElementById('probe-smtp-accepted').innerText = s.smtp.accepted_count;
    document.getElementById('probe-smtp-failed').innerText = s.smtp.failed_count;

    // Google
    const googleBadge = document.getElementById('probe-google-badge');
    if (googleBadge) {
      googleBadge.className = s.google_calendar.authorized ? 'badge badge-approved' : 'badge badge-pending';
      googleBadge.innerText = s.google_calendar.authorized ? 'Authorized' : 'Setup Required';
    }
    document.getElementById('probe-google-desc').innerText = s.google_calendar.status_text;

    // Ollama
    const ollamaBadge = document.getElementById('probe-ollama-badge');
    if (ollamaBadge) {
      ollamaBadge.className = s.ollama_ai.connected ? 'badge badge-approved' : 'badge badge-pending';
      ollamaBadge.innerText = s.ollama_ai.connected ? 'Active' : 'Fallback Engine';
    }
    document.getElementById('probe-ollama-desc').innerText = `${s.ollama_ai.status_text} (Model: ${s.ollama_ai.active_model})`;

    showToast('Probes refreshed.', 'info');
  } catch (err) {
    showToast(`Failed to load integration status: ${err.message}`, 'error');
  }
}

// 10. OLLAMA TESTING
async function testOllamaPrompt() {
  const prompt = document.getElementById('ollama-test-prompt').value.trim();
  if (!prompt) {
    showToast('Please enter a test prompt.', 'warning');
    return;
  }
  const btn = document.getElementById('btn-test-ollama');
  const resultDiv = document.getElementById('ollama-test-result');
  btn.disabled = true;
  btn.innerText = 'Querying AI...';
  resultDiv.style.display = 'block';
  resultDiv.innerText = 'Connecting to Local AI engine...';

  try {
    const res = await api.post('/ollama/test', { prompt });
    resultDiv.innerText = `[Source: ${res.source}]\n\n${res.response}`;
  } catch (err) {
    resultDiv.innerText = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = 'Run AI Test';
  }
}

// 11. AUDIT LOGS
async function loadAuditLogs() {
  try {
    const logs = await api.get('/admin/audit-logs');
    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';
    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No logs found.</td></tr>';
      return;
    }
    logs.forEach(l => {
      tbody.innerHTML += `
        <tr>
          <td>#${l.id}</td>
          <td style="font-size: 12px; color: var(--text-muted);">${new Date(l.created_at).toLocaleString()}</td>
          <td><span class="badge badge-submitted">${l.action}</span></td>
          <td><strong>${l.entity}</strong> ${l.entity_id ? `(${l.entity_id})` : ''}</td>
          <td style="font-size: 12.5px;">${l.details}</td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load audit logs: ${err.message}`, 'error');
  }
}

// ==========================================
// 12. AUTOMATION CONTROL CENTER
// ==========================================
async function loadAutomationOverview() {
  try {
    const status = await api.get('/automation/status');
    
    document.getElementById('auto-active-workflows').innerText = status.workflows.active;
    document.getElementById('auto-completed-workflows').innerText = status.workflows.completed;
    document.getElementById('auto-pending-jobs').innerText = status.jobs.pending;
    document.getElementById('auto-failed-jobs').innerText = status.jobs.failed;

    document.getElementById('auto-next-exec').innerText = status.next_execution ? new Date(status.next_execution).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ` (${status.next_job_type || 'job'})` : 'No pending jobs';
    document.getElementById('auto-last-exec').innerText = status.last_execution ? new Date(status.last_execution).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ` (${status.last_job_type || 'completed'})` : 'Awaiting initial trigger';

    // Load intern workflow states
    const interns = await api.get('/admin/interns');
    const tbody = document.getElementById('workflow-interns-tbody');
    tbody.innerHTML = '';

    if (!interns || interns.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No interns registered.</td></tr>';
      return;
    }

    interns.forEach(i => {
      const isPaused = i.workflow_paused || i.workflow_status === 'paused';
      const isCompleted = i.status === 'completed' || i.workflow_status === 'completed';

      let stateBadge = '';
      if (isCompleted) {
        stateBadge = '<span class="badge badge-approved">COMPLETED</span>';
      } else if (isPaused) {
        stateBadge = '<span class="badge" style="background: #FEF3C7; color: #92400E;">PAUSED</span>';
      } else {
        stateBadge = '<span class="badge badge-submitted">ACTIVE RUNNER</span>';
      }

      let actions = '';
      if (!isCompleted) {
        if (isPaused) {
          actions += `<button class="btn btn-primary btn-sm" style="padding: 3px 8px; font-size: 11.5px; margin-right: 6px;" onclick="resumeWorkflow(${i.id})">▶ Resume</button>`;
        } else {
          actions += `<button class="btn btn-secondary btn-sm" style="padding: 3px 8px; font-size: 11.5px; margin-right: 6px;" onclick="pauseWorkflow(${i.id})">⏸ Pause</button>`;
        }
        actions += `<button class="btn btn-secondary btn-sm" style="padding: 3px 8px; font-size: 11.5px; color: #DC2626;" onclick="cancelWorkflow(${i.id})">✕ Cancel</button>`;
      } else {
        actions = `<span style="font-size: 12px; color: var(--text-muted);">Certified ✓</span>`;
      }

      tbody.innerHTML += `
        <tr>
          <td>
            <strong>${i.name}</strong>
            <div style="font-size: 11px; color: var(--text-muted);">${i.intern_code}</div>
          </td>
          <td><span class="badge" style="background: #E2E8F0; color: #1E293B;">${i.domain}</span></td>
          <td>Week ${i.current_week} of ${i.duration_weeks}</td>
          <td>${stateBadge}</td>
          <td>${actions}</td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load automation overview: ${err.message}`, 'error');
  }
}

async function loadAutomationJobs() {
  const filter = document.getElementById('auto-jobs-filter')?.value || '';
  const tbody = document.getElementById('auto-jobs-table-body');
  if (!tbody) return;

  try {
    const endpoint = filter ? `/automation/jobs?status=${filter}&limit=60` : '/automation/jobs?limit=60';
    const jobs = await api.get(endpoint);
    tbody.innerHTML = '';

    if (!jobs || jobs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No automation jobs in queue.</td></tr>';
      return;
    }

    jobs.forEach(j => {
      let statusBadge = '';
      if (j.status === 'completed') statusBadge = '<span class="badge badge-approved">COMPLETED</span>';
      else if (j.status === 'pending') statusBadge = '<span class="badge badge-submitted">PENDING</span>';
      else if (j.status === 'failed') statusBadge = '<span class="badge badge-rejected">FAILED</span>';
      else statusBadge = `<span class="badge">${j.status.toUpperCase()}</span>`;

      const schedStr = j.scheduled_at ? new Date(j.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-';
      const msg = j.error_message ? `<span style="color: #DC2626; font-size: 11px;">${j.error_message.substring(0, 50)}...</span>` : (j.status === 'completed' ? '<span style="color: #059669; font-size: 11px;">Executed successfully</span>' : '<span style="color: var(--text-muted); font-size: 11px;">Awaiting time gate</span>');

      let actionBtn = '';
      if (j.status === 'failed' || j.status === 'pending') {
        actionBtn = `<button class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size: 11px;" onclick="triggerRetryJob(${j.id})">⚡ Run / Retry</button>`;
      } else {
        actionBtn = `<span style="color: var(--text-muted); font-size: 11px;">✓</span>`;
      }

      tbody.innerHTML += `
        <tr>
          <td>#${j.id}</td>
          <td><strong>${j.intern_name || 'System'}</strong></td>
          <td><code style="font-size: 11.5px; color: var(--primary);">${j.job_type}</code></td>
          <td style="font-size: 12px;">${schedStr}</td>
          <td>${statusBadge}</td>
          <td>${j.retry_count} / ${j.max_retries}</td>
          <td style="max-width: 200px;">${msg}</td>
          <td>${actionBtn}</td>
        </tr>
      `;
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Error: ${err.message}</td></tr>`;
  }
}

async function triggerRetryJob(jobId) {
  try {
    const res = await api.post(`/automation/jobs/${jobId}/retry`, {});
    showToast(`Job #${jobId} triggered successfully.`, 'success');
    await loadAutomationJobs();
    await loadAutomationOverview();
  } catch (err) {
    showToast(`Job retry failed: ${err.message}`, 'error');
  }
}

async function triggerRunPendingJobs() {
  const btn = document.getElementById('btn-trigger-pending');
  if (btn) {
    btn.disabled = true;
    btn.innerText = 'Processing Queue...';
  }

  try {
    const res = await api.post('/automation/run-pending', {});
    showToast(`Executed ${res.executed} job(s) (${res.skipped_paused} skipped paused).`, 'success');
    await loadAutomationJobs();
    await loadAutomationOverview();
  } catch (err) {
    showToast(`Queue runner failed: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = '⚡ Run Pending Jobs Now';
    }
  }
}

async function pauseWorkflow(internId) {
  try {
    await api.post(`/automation/workflows/${internId}/pause`, {});
    showToast(`Workflow paused for Intern #${internId}.`, 'info');
    await loadAutomationOverview();
  } catch (err) {
    showToast(`Failed to pause workflow: ${err.message}`, 'error');
  }
}

async function resumeWorkflow(internId) {
  try {
    await api.post(`/automation/workflows/${internId}/resume`, {});
    showToast(`Workflow resumed for Intern #${internId}.`, 'success');
    await loadAutomationOverview();
  } catch (err) {
    showToast(`Failed to resume workflow: ${err.message}`, 'error');
  }
}

async function cancelWorkflow(internId) {
  if (!confirm(`Are you sure you want to cancel the automated workflow for Intern #${internId}? Pending automated tasks will be stopped.`)) {
    return;
  }

  try {
    await api.post(`/automation/workflows/${internId}/cancel`, {});
    showToast(`Workflow cancelled for Intern #${internId}.`, 'warning');
    await loadAutomationOverview();
    await loadAutomationJobs();
  } catch (err) {
    showToast(`Failed to cancel workflow: ${err.message}`, 'error');
  }
}

async function loadAtRiskInterns() {
  const tbody = document.getElementById('at-risk-table-body');
  const badge = document.getElementById('at-risk-count-badge');
  if (!tbody) return;

  try {
    const data = await api.get('/automation/analytics/advanced');
    const atRisk = data.at_risk_interns || [];

    if (badge) badge.innerText = `${atRisk.length} At-Risk`;

    tbody.innerHTML = '';
    if (atRisk.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #065F46; padding: 20px;">✓ All active interns are on schedule. No overdue milestones or low evaluation scores detected.</td></tr>';
      return;
    }

    atRisk.forEach(r => {
      const urgencyBadge = r.urgency === 'High' 
        ? '<span class="badge" style="background: #FEE2E2; color: #991B1B;">HIGH URGENCY</span>'
        : '<span class="badge" style="background: #FEF3C7; color: #92400E;">MODERATE</span>';

      const factorTags = r.risk_factors.map(f => `<span class="badge" style="background: #F1F5F9; color: #334155; margin-right: 4px; font-size: 11px;">${f}</span>`).join('');

      tbody.innerHTML += `
        <tr>
          <td>
            <strong>${r.name}</strong>
            <div style="font-size: 11px; color: var(--text-muted);">${r.intern_code}</div>
          </td>
          <td><span class="badge" style="background: #E2E8F0; color: #1E293B;">${r.domain}</span></td>
          <td>Week ${r.current_week}</td>
          <td><strong style="color: ${r.total_score >= 60 ? 'var(--primary)' : 'var(--accent)'};">${r.total_score}</strong> / 100</td>
          <td>${factorTags}</td>
          <td>${urgencyBadge}</td>
        </tr>
      `;
    });
  } catch (err) {
    console.error('Failed to load at-risk analytics:', err);
  }
}

async function loadAutomationScheduleConfig() {
  try {
    const cfg = await api.get('/automation/settings');
    if (document.getElementById('cfg-review-day')) document.getElementById('cfg-review-day').value = cfg.review_day || 'Sunday';
    if (document.getElementById('cfg-review-time')) document.getElementById('cfg-review-time').value = cfg.review_time || '16:00';
    if (document.getElementById('cfg-deadline-offset')) document.getElementById('cfg-deadline-offset').value = cfg.submission_deadline_day_offset || 6;
    if (document.getElementById('cfg-reminder-offset')) document.getElementById('cfg-reminder-offset').value = cfg.task_reminder_day_offset || 5;
    if (document.getElementById('cfg-extension-days')) document.getElementById('cfg-extension-days').value = cfg.resubmission_extension_days || 2;
    if (document.getElementById('cfg-timezone')) document.getElementById('cfg-timezone').value = cfg.timezone || 'UTC';
  } catch (err) {
    console.error('Failed to load automation settings:', err);
  }
}

async function handleSaveAutomationSchedule(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-save-schedule');
  if (btn) btn.disabled = true;

  const payload = {
    review_day: document.getElementById('cfg-review-day').value,
    review_time: document.getElementById('cfg-review-time').value,
    submission_deadline_day_offset: parseInt(document.getElementById('cfg-deadline-offset').value),
    task_reminder_day_offset: parseInt(document.getElementById('cfg-reminder-offset').value),
    resubmission_extension_days: parseInt(document.getElementById('cfg-extension-days').value),
    timezone: document.getElementById('cfg-timezone').value
  };

  try {
    await api.put('/automation/settings', payload);
    showToast('Automation schedule parameters updated successfully.', 'success');
    closeModal('automation-schedule-modal');
  } catch (err) {
    showToast(`Failed to update schedule: ${err.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ==========================================
// 13. CERTIFICATES & VERIFICATION
// ==========================================
async function loadCertificatesRoster() {
  const tbody = document.getElementById('certificates-table-body');
  if (!tbody) return;

  try {
    const certs = await api.get('/certificates/roster');
    tbody.innerHTML = '';

    if (!certs || certs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">No completion certificates issued yet. Issue certificates once interns fulfill milestone criteria.</td></tr>';
      return;
    }

    certs.forEach(c => {
      tbody.innerHTML += `
        <tr>
          <td>
            <a href="/verify/${c.certificate_number}" target="_blank" style="font-weight: 700; color: var(--primary); text-decoration: none;">
              ${c.certificate_number} ↗
            </a>
          </td>
          <td><strong>${c.intern_name}</strong></td>
          <td><span class="badge" style="background: #E2E8F0; color: #1E293B;">${c.domain}</span></td>
          <td><strong style="color: #065F46;">${c.grade}</strong></td>
          <td style="font-size: 12px;">${c.issue_date}</td>
          <td><code style="font-size: 11px; color: var(--text-muted);">${c.verification_hash}</code></td>
          <td>
            <a href="${c.download_url}" target="_blank" class="btn btn-secondary btn-sm" style="padding: 3px 8px; font-size: 11px; text-decoration: none; margin-right: 4px;">
              📥 PDF
            </a>
            <a href="/verify/${c.certificate_number}" target="_blank" class="btn btn-primary btn-sm" style="padding: 3px 8px; font-size: 11px; text-decoration: none;">
              🔍 Verify
            </a>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Error: ${err.message}</td></tr>`;
  }
}

async function openIssueCertificateModal() {
  const select = document.getElementById('issue-cert-intern-select');
  select.innerHTML = '<option value="">-- Choose an intern --</option>';

  try {
    const interns = await api.get('/admin/interns');
    interns.forEach(i => {
      select.innerHTML += `<option value="${i.id}">${i.name} (${i.intern_code}) — ${i.domain} [Score: ${i.total_score}]</option>`;
    });
    document.getElementById('cert-eligibility-preview').style.display = 'none';
    openModal('issue-certificate-modal');
  } catch (err) {
    showToast(`Failed to load intern list: ${err.message}`, 'error');
  }
}

async function checkSelectedInternEligibility() {
  const internId = document.getElementById('issue-cert-intern-select').value;
  const preview = document.getElementById('cert-eligibility-preview');
  const title = document.getElementById('cert-eligibility-title');
  const desc = document.getElementById('cert-eligibility-desc');

  if (!internId) {
    preview.style.display = 'none';
    return;
  }

  try {
    const res = await api.get(`/certificates/eligibility/${internId}`);
    preview.style.display = 'block';

    if (res.eligible) {
      preview.style.background = '#ECFDF5';
      preview.style.border = '1px solid #A7F3D0';
      title.style.color = '#065F46';
      title.innerText = `✓ Eligible for Certification (Grade: ${res.suggested_grade})`;
      desc.innerText = `${res.approved_tasks} of ${res.total_tasks} milestones certified. Cumulative Score: ${res.total_score}/100.`;
    } else {
      preview.style.background = '#FFFBEB';
      preview.style.border = '1px solid #FDE68A';
      title.style.color = '#92400E';
      title.innerText = `⚠️ Partial Progress (Admin Approval Allowed)`;
      desc.innerText = `${res.reason} (Total score: ${res.total_score}/100). Admin may still issue certificate with override.`;
    }
  } catch (err) {
    console.error('Eligibility check error:', err);
  }
}

async function handleIssueCertificate(e) {
  e.preventDefault();
  const internId = document.getElementById('issue-cert-intern-select').value;
  const btn = document.getElementById('btn-confirm-issue-cert');

  if (!internId) {
    showToast('Please select an intern.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerText = 'Generating PDF Certificate with QR...';

  try {
    const res = await api.post(`/certificates/issue/${internId}`, {});
    showToast(`Certificate ${res.certificate_number} generated and issued successfully!`, 'success');
    closeModal('issue-certificate-modal');
    await loadCertificatesRoster();
  } catch (err) {
    showToast(`Certificate issuance failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Generate & Issue Certificate';
  }
}
