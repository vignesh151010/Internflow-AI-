/**
 * InternFlow AI - Intern Portal Logic
 * Phase 1 & 2 Complete Implementation
 */

let internProfile = null;
let currentTasks = [];

window.addEventListener('DOMContentLoaded', async () => {
  const user = api.getUser();
  const token = api.getToken();

  if (!token || !user || user.role !== 'intern') {
    api.clearAuth();
    window.location.href = '/';
    return;
  }

  await loadInternData();
  await loadInternRoadmap();
  await loadInternTasks();
  await loadInternFeedback();
  await loadInternMeetings();
  await loadInternAttendance();
  await loadInternCertificate();
});

function handleInternLogout() {
  api.clearAuth();
  window.location.href = '/';
}

function showInternSection(sectionName) {
  document.querySelectorAll('.intern-view').forEach(v => v.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const target = document.getElementById(`intern-section-${sectionName}`);
  if (target) {
    target.style.display = 'block';
  }

  const navItems = Array.from(document.querySelectorAll('.nav-item'));
  const activeNav = navItems.find(item => item.getAttribute('onclick')?.includes(sectionName));
  if (activeNav) activeNav.classList.add('active');

  const titles = {
    overview: 'Internship Workspace & Summary',
    roadmap: 'Personalized Weekly Roadmap',
    tasks: 'Assigned Milestone Deliverables',
    feedback: 'Mentor Evaluations & Score History',
    mentor: 'AI Technical Project Mentor',
    attendance: 'Daily Attendance Records',
    certificate: 'Verified Certificate of Completion'
  };
  document.getElementById('intern-section-title').innerText = titles[sectionName] || 'Internship Workspace';

  if (sectionName === 'roadmap') loadInternRoadmap();
  else if (sectionName === 'tasks') loadInternTasks();
  else if (sectionName === 'feedback') loadInternFeedback();
  else if (sectionName === 'mentor') loadInternChatHistory();
  else if (sectionName === 'attendance') loadInternAttendance();
  else if (sectionName === 'certificate') loadInternCertificate();
}

async function loadInternData() {
  try {
    const p = await api.get('/intern/profile');
    internProfile = p;

    document.getElementById('intern-sidebar-name').innerText = p.name;
    document.getElementById('intern-sidebar-code').innerText = p.intern_code;
    document.getElementById('intern-avatar').innerText = p.name.substring(0, 2).toUpperCase();

    document.getElementById('intern-domain-badge').innerText = p.domain;
    document.getElementById('intern-status-badge').innerText = p.status.toUpperCase();

    document.getElementById('intern-project-title').innerText = p.main_task;
    document.getElementById('intern-project-desc').innerText = p.task_description || 'Focus on your weekly roadmap deliverables to complete this project.';
    document.getElementById('intern-overall-score').innerText = p.total_score > 0 ? p.total_score : '0.0';

    document.getElementById('intern-start-date').innerText = p.start_date;
    document.getElementById('intern-end-date').innerText = p.end_date;
    document.getElementById('intern-duration').innerText = `${p.duration_weeks} Weeks`;
    document.getElementById('intern-curr-week').innerText = `Week ${p.current_week}`;

    document.getElementById('intern-progress-text').innerText = `${p.progress_percentage}%`;
    document.getElementById('intern-progress-fill').style.width = `${p.progress_percentage}%`;
    document.getElementById('intern-tasks-completed-text').innerText = `${p.completed_tasks_count} of ${p.tasks_count} Milestones certified`;
  } catch (err) {
    showToast(`Failed to load profile: ${err.message}`, 'error');
  }
}

async function loadInternRoadmap() {
  const container = document.getElementById('intern-roadmap-container');
  try {
    const roadmaps = await api.get('/intern/roadmap');
    container.innerHTML = '';

    if (!roadmaps || roadmaps.length === 0) {
      container.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 30px 0;">Your weekly roadmap is currently being compiled by the AI engine.</p>';
      return;
    }

    roadmaps.forEach((r, idx) => {
      const card = document.createElement('div');
      card.className = idx === 0 ? 'week-card open' : 'week-card';

      let taskListHtml = '';
      if (r.tasks && r.tasks.length > 0) {
        r.tasks.forEach(t => {
          let statusBadge = `<span class="badge badge-${t.status}">${t.status.toUpperCase()}</span>`;
          taskListHtml += `
            <div style="background: white; border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 14px; margin-top: 10px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <strong style="color: var(--primary);">${t.title}</strong>
                ${statusBadge}
              </div>
              <p style="font-size: 13px; color: #475569; margin-bottom: 8px;">${t.description}</p>
              <div style="display: flex; justify-content: space-between; font-size: 11.5px; color: var(--text-muted);">
                <span>Tech: <strong style="color: var(--secondary);">${t.technologies || 'Standard'}</strong></span>
                <span>Deadline: ${t.deadline ? new Date(t.deadline).toLocaleDateString() : 'N/A'}</span>
              </div>
            </div>
          `;
        });
      }

      card.innerHTML = `
        <div class="week-card-header" onclick="this.parentElement.classList.toggle('open')">
          <div>
            <span style="font-weight: 700; color: var(--primary);">Week ${r.week_number}:</span>
            <span style="font-weight: 600; margin-left: 6px;">${r.title}</span>
            <span style="font-size: 12px; color: var(--text-muted); margin-left: 8px;">(${r.theme || ''})</span>
          </div>
          <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">${r.estimated_hours} hrs</span>
        </div>
        <div class="week-card-body">
          <div style="margin-bottom: 8px; font-size: 13px; color: var(--text-muted);">
            <strong>Key Objectives:</strong> ${r.objectives || ''}
          </div>
          <div style="margin-bottom: 8px; font-size: 13px; color: var(--text-muted);">
            <strong>Deliverables:</strong> ${r.key_deliverables || ''}
          </div>
          ${taskListHtml}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    showToast(`Failed to load roadmap: ${err.message}`, 'error');
  }
}

async function loadInternTasks() {
  const container = document.getElementById('intern-tasks-list');
  const previewBox = document.getElementById('intern-current-task-preview');

  try {
    const tasks = await api.get('/intern/tasks');
    currentTasks = tasks;
    container.innerHTML = '';

    if (!tasks || tasks.length === 0) {
      container.innerHTML = '<p style="text-align: center; color: var(--text-muted); padding: 30px 0;">No tasks assigned yet.</p>';
      if (previewBox) previewBox.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No pending tasks.</p>';
      return;
    }

    // Set preview box on overview
    if (previewBox) {
      const activeTask = tasks.find(t => t.status === 'pending' || t.status === 'needs_resubmission' || t.status === 'submitted') || tasks[0];
      previewBox.innerHTML = `
        <div style="font-weight: 700; color: var(--primary); margin-bottom: 4px;">Week ${activeTask.week_number}: ${activeTask.title}</div>
        <div style="font-size: 12.5px; color: #475569; margin-bottom: 8px;">${(activeTask.description || '').substring(0, 140)}...</div>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
          <span class="badge badge-${activeTask.status}">${activeTask.status.replace('_', ' ').toUpperCase()}</span>
          <span>Deadline: ${activeTask.deadline ? new Date(activeTask.deadline).toLocaleDateString() : 'N/A'}</span>
        </div>
      `;
    }

    tasks.forEach(t => {
      let actionBtn = '';
      if (t.status === 'pending') {
        actionBtn = `<button class="btn btn-primary btn-sm" onclick="openSubmitModal(${t.id}, '${escapeQuotes(t.title)}')">Submit Work ↗</button>`;
      } else if (t.status === 'needs_resubmission' || t.status === 'rejected') {
        const nextVer = t.submission ? (t.submission.version + 1) : 2;
        actionBtn = `<button class="btn btn-warning btn-sm" style="background: var(--accent); color: white;" onclick="openSubmitModal(${t.id}, '${escapeQuotes(t.title)}', true)">Resubmit Work (v${nextVer}) ↗</button>`;
      } else if (t.status === 'submitted') {
        actionBtn = `<span class="badge badge-submitted">Under Review</span>`;
      } else if (t.status === 'approved') {
        actionBtn = `<span class="badge badge-approved">✓ Approved</span>`;
      }

      let resubmissionAlert = '';
      if (t.status === 'needs_resubmission') {
        resubmissionAlert = `
          <div style="margin-top: 12px; padding: 12px 16px; background: #FFFBEB; border-left: 4px solid #F59E0B; border-radius: var(--radius-sm); font-size: 13px; color: #92400E;">
            <strong>⚠️ Revision Requested:</strong> The mentor has reviewed your submission and requested adjustments before final certification. Please review the feedback below, revise your solution, and resubmit.
          </div>
        `;
      }

      let subSection = '';
      if (t.submission) {
        const sub = t.submission;
        subSection = `
          <div style="margin-top: 12px; padding: 12px; background: #F1F5F9; border-radius: var(--radius-sm); font-size: 12px;">
            <div style="display: flex; justify-content: space-between; font-weight: 600; align-items: center;">
              <span>
                <span class="badge badge-submitted" style="font-size: 10px; margin-right: 6px;">v${sub.version || 1}</span>
                Your Submission:
              </span>
              <span>Submitted ${new Date(sub.submitted_at).toLocaleDateString()}</span>
            </div>
            ${sub.file_path ? `
              <div style="margin-top: 6px; display: flex; align-items: center; gap: 6px;">
                <span style="font-weight: 600; color: #1E293B;">📎 Uploaded Deliverable:</span>
                <span class="badge" style="background: #E2E8F0; color: #1E293B; font-size: 11px;">${sub.file_type ? sub.file_type.toUpperCase() : 'FILE'}</span>
                <span style="font-family: monospace; color: #475569; font-size: 11px;">${sub.file_path.split(/[\\\\/]/).pop()}</span>
              </div>
            ` : ''}
            ${sub.submission_link ? `<div style="margin-top: 4px;"><a href="${sub.submission_link}" target="_blank" style="color: var(--secondary); font-weight: 600;">🔗 Repository / Link: ${sub.submission_link}</a></div>` : ''}
            <div style="margin-top: 4px; color: var(--text-muted); font-style: italic;">"${sub.notes || 'No comments provided'}"</div>
          </div>
        `;
      }

      let evalSection = '';
      if (t.evaluation) {
        const isResub = t.evaluation.final_status === 'needs_resubmission';
        evalSection = `
          <div style="margin-top: 10px; padding: 12px; background: ${isResub ? '#FEF3C7' : '#ECFDF5'}; border: 1px solid ${isResub ? '#FDE68A' : '#A7F3D0'}; border-radius: var(--radius-sm); font-size: 12.5px;">
            <div style="display: flex; justify-content: space-between; font-weight: 700; color: ${isResub ? '#B45309' : '#065F46'};">
              <span>Evaluation Score: ${t.evaluation.score}/100 (${t.evaluation.final_status ? t.evaluation.final_status.replace('_', ' ').toUpperCase() : 'EVALUATED'})</span>
              <span>${isResub ? 'Revisions Required' : 'Certified'}</span>
            </div>
            <div style="margin-top: 6px; color: ${isResub ? '#92400E' : '#064E3B'};"><strong>Feedback:</strong> ${t.evaluation.feedback}</div>
            ${t.evaluation.strengths ? `<div style="margin-top: 4px; color: #065F46;"><strong>Strengths:</strong> ${t.evaluation.strengths}</div>` : ''}
            ${t.evaluation.improvements ? `<div style="margin-top: 4px; color: #92400E;"><strong>Areas for Improvement:</strong> ${t.evaluation.improvements}</div>` : ''}
          </div>
        `;
      }

      container.innerHTML += `
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-header">
            <div>
              <span class="badge badge-submitted">Week ${t.week_number}</span>
              <span class="card-title" style="display: inline; margin-left: 8px;">${t.title}</span>
            </div>
            <div>${actionBtn}</div>
          </div>

          ${resubmissionAlert}

          <p style="font-size: 13.5px; color: var(--text-main); margin-bottom: 16px; margin-top: 12px;">${t.description}</p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 12.5px;">
            <div style="background: #F8FAFC; padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <strong style="color: var(--primary);">Step-by-Step Instructions:</strong>
              <div style="white-space: pre-line; margin-top: 6px; color: #334155;">${t.instructions || 'Follow project specs.'}</div>
            </div>

            <div style="background: #F8FAFC; padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <strong style="color: var(--primary);">Recommended Technologies:</strong>
              <div style="color: var(--secondary); font-weight: 600; margin-top: 4px;">${t.technologies || 'Python / Web Stack'}</div>
              
              <strong style="display: block; margin-top: 10px; color: var(--primary);">Expected Output:</strong>
              <div style="color: #334155; margin-top: 4px;">${t.expected_output || 'Functional tested code.'}</div>

              <strong style="display: block; margin-top: 10px; color: var(--primary);">Submission Requirements:</strong>
              <div style="color: #334155; margin-top: 4px;">${t.submission_requirements || 'GitHub URL and notes.'}</div>
            </div>
          </div>

          ${subSection}
          ${evalSection}
        </div>
      `;
    });
  } catch (err) {
    showToast(`Failed to load tasks: ${err.message}`, 'error');
  }
}

function escapeQuotes(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'");
}

function openSubmitModal(taskId, taskTitle, isResubmit = false) {
  document.getElementById('submit-task-id').value = taskId;
  document.getElementById('submit-modal-title').innerText = isResubmit ? `Resubmit Deliverables: ${taskTitle}` : `Submit: ${taskTitle}`;
  const fileInput = document.getElementById('submit-file');
  if (fileInput) fileInput.value = '';
  document.getElementById('submit-link').value = '';
  document.getElementById('submit-notes').value = '';
  openModal('intern-submit-modal');
}

async function handleTaskSubmission(e) {
  e.preventDefault();
  const taskId = document.getElementById('submit-task-id').value;
  const link = document.getElementById('submit-link').value.trim();
  const notes = document.getElementById('submit-notes').value.trim();
  const fileInput = document.getElementById('submit-file');
  const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
  const btn = document.getElementById('btn-intern-submit-btn');

  if (!file && !link && !notes) {
    showToast('Please provide at least a deliverable file or repository link.', 'warning');
    return;
  }

  // Validate file size client-side if file is provided (25MB max)
  if (file && file.size > 25 * 1024 * 1024) {
    showToast('Uploaded file exceeds 25 MB limit.', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerText = 'Uploading Deliverables...';

  try {
    const formData = new FormData();
    if (file) formData.append('file', file);
    if (link) formData.append('submission_link', link);
    if (notes) formData.append('notes', notes);

    const res = await api.upload(`/intern/tasks/${taskId}/submit`, formData);
    showToast(res.message || 'Deliverables submitted successfully! Your mentor will review them shortly.', 'success');
    closeModal('intern-submit-modal');
    await loadInternTasks();
    await loadInternData();
    await loadInternFeedback();
  } catch (err) {
    showToast(`Submission failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Submit Work for Review';
  }
}

async function loadInternFeedback() {
  const tbody = document.getElementById('intern-feedback-tbody');
  const previewBox = document.getElementById('intern-recent-feedback-preview');

  try {
    const subs = await api.get('/intern/submissions');
    tbody.innerHTML = '';

    const evaluatedSubs = subs.filter(s => s.evaluation);

    if (previewBox) {
      if (evaluatedSubs.length > 0) {
        const latest = evaluatedSubs[0];
        previewBox.innerHTML = `
          <div style="font-weight: 700; color: var(--primary); margin-bottom: 4px;">${latest.task_title} (v${latest.version || 1})</div>
          <div style="font-size: 13px; font-weight: 700; color: ${latest.evaluation.score >= 70 ? 'var(--success)' : 'var(--accent)'}; margin-bottom: 6px;">Score: ${latest.evaluation.score}/100</div>
          <div style="font-size: 12.5px; color: #475569;">"${(latest.evaluation.feedback || '').substring(0, 120)}..."</div>
        `;
      } else {
        previewBox.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No evaluations recorded yet.</p>';
      }
    }

    if (evaluatedSubs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No evaluations available yet. Submit tasks to receive mentor feedback.</td></tr>';
      return;
    }

    evaluatedSubs.forEach(s => {
      tbody.innerHTML += `
        <tr>
          <td style="font-weight: 600;">Week ${s.week_number}: ${s.task_title} <span class="badge badge-submitted" style="font-size: 10px;">v${s.version || 1}</span></td>
          <td style="font-size: 12px; color: var(--text-muted);">${new Date(s.submitted_at).toLocaleDateString()}</td>
          <td><strong style="color: var(--primary); font-size: 15px;">${s.evaluation.score}</strong>/100</td>
          <td style="max-width: 250px;">${s.evaluation.feedback}</td>
          <td style="color: #065F46; font-size: 12.5px;">${s.evaluation.strengths || '-'}</td>
          <td style="color: #92400E; font-size: 12.5px;">${s.evaluation.improvements || '-'}</td>
        </tr>
      `;
    });
  } catch (err) {
    showToast(`Failed to load feedback: ${err.message}`, 'error');
  }
}

async function loadInternMeetings() {
  const preview = document.getElementById('intern-meetings-preview');
  const badge = document.getElementById('intern-meeting-badge');
  if (!preview) return;

  try {
    const meetings = await api.get('/intern/meetings');
    if (badge) badge.innerText = `${meetings.length} Scheduled`;

    if (!meetings || meetings.length === 0) {
      preview.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No upcoming review meetings scheduled yet.</p>';
      return;
    }

    preview.innerHTML = '';
    meetings.forEach(m => {
      const meetLink = m.google_meet_url || m.meeting_link;
      const d = new Date(m.scheduled_time);
      const timeStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      let joinBtn = '';
      if (meetLink) {
        joinBtn = `<a href="${meetLink}" target="_blank" class="btn btn-primary btn-sm" style="text-decoration: none; padding: 4px 10px; font-size: 12px; background: #059669;">🎥 Join Google Meet</a>`;
      } else {
        joinBtn = `<span class="badge badge-submitted" style="font-size: 11px;">Link Pending</span>`;
      }

      preview.innerHTML += `
        <div style="background: #F8FAFC; border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
            <strong style="color: var(--primary); font-size: 13.5px;">${m.title}</strong>
            ${joinBtn}
          </div>
          <div style="font-size: 12px; color: #475569; margin-bottom: 4px;">${m.description || 'Sprint & Progress review session with Lead Mentor.'}</div>
          <div style="display: flex; justify-content: space-between; font-size: 11.5px; color: var(--text-muted);">
            <span>📅 ${timeStr} (${m.duration_minutes} min)</span>
            <span class="badge" style="background: #E2E8F0; color: #1E293B;">${(m.meeting_type || 'Review').toUpperCase()}</span>
          </div>
        </div>
      `;
    });
  } catch (err) {
    if (preview) preview.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">Could not load meetings: ${err.message}</p>`;
  }
}

async function loadInternAttendance() {
  const tbody = document.getElementById('intern-attendance-tbody');
  const preview = document.getElementById('intern-attendance-preview');
  const btnQuick = document.getElementById('btn-checkin-quick');
  const btnTab = document.getElementById('btn-checkin-tab');

  try {
    const records = await api.get('/intern/attendance');
    const todayStr = new Date().toISOString().split('T')[0];
    const checkedToday = records && records.some(r => r.date === todayStr);

    if (checkedToday) {
      if (btnQuick) {
        btnQuick.disabled = true;
        btnQuick.innerText = '✓ Checked In Today';
        btnQuick.className = 'btn btn-secondary btn-sm';
      }
      if (btnTab) {
        btnTab.disabled = true;
        btnTab.innerText = '✓ Checked In Today';
        btnTab.className = 'btn btn-secondary btn-sm';
      }
      if (preview) {
        preview.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge badge-approved" style="font-size: 13px;">✓ Marked Present</span>
            <span style="font-size: 12.5px; color: var(--text-muted);">Your attendance for today (${todayStr}) is confirmed.</span>
          </div>
        `;
      }
    } else {
      if (btnQuick) {
        btnQuick.disabled = false;
        btnQuick.innerText = 'Check In Today';
        btnQuick.className = 'btn btn-primary btn-sm';
      }
      if (btnTab) {
        btnTab.disabled = false;
        btnTab.innerText = 'Check In Today';
        btnTab.className = 'btn btn-primary btn-sm';
      }
      if (preview) {
        preview.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge badge-submitted" style="font-size: 12px; background: #FEF3C7; color: #92400E;">Pending Check-In</span>
            <span style="font-size: 12.5px; color: #475569;">Click "Check In Today" to log your active session.</span>
          </div>
        `;
      }
    }

    if (tbody) {
      tbody.innerHTML = '';
      if (!records || records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No attendance records logged yet. Check in to record your presence.</td></tr>';
        return;
      }

      records.forEach(r => {
        tbody.innerHTML += `
          <tr>
            <td style="font-weight: 600;">${r.date}</td>
            <td><span class="badge badge-${r.status === 'present' ? 'approved' : 'submitted'}">${r.status.toUpperCase()}</span></td>
            <td style="color: var(--text-muted); font-size: 12.5px;">${r.notes || 'Daily portal check-in'}</td>
          </tr>
        `;
      });
    }
  } catch (err) {
    if (preview) preview.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">Attendance check unavailable.</p>`;
  }
}

async function handleDailyCheckIn() {
  const btnQuick = document.getElementById('btn-checkin-quick');
  const btnTab = document.getElementById('btn-checkin-tab');

  if (btnQuick) btnQuick.disabled = true;
  if (btnTab) btnTab.disabled = true;

  try {
    const res = await api.post('/intern/attendance/check-in', {});
    showToast(res.message || 'Attendance logged successfully for today!', 'success');
    await loadInternAttendance();
  } catch (err) {
    showToast(`Check-in failed: ${err.message}`, 'error');
    if (btnQuick) btnQuick.disabled = false;
    if (btnTab) btnTab.disabled = false;
  }
}

async function loadInternChatHistory() {
  const container = document.getElementById('intern-chat-messages');
  if (!container) return;

  try {
    const history = await api.get('/intern/chat/history');
    if (history && history.length > 0) {
      container.innerHTML = '';
      history.forEach(m => {
        const bubble = document.createElement('div');
        bubble.className = m.role === 'user' ? 'chat-msg user' : 'chat-msg ai';
        bubble.innerHTML = m.role === 'assistant' ? m.content.replace(/\n/g, '<br>') : escapeQuotes(m.content);
        container.appendChild(bubble);
      });
      container.scrollTop = container.scrollHeight;
    }
  } catch (err) {
    console.error('Failed to load chat history:', err);
  }
}

async function clearInternChatHistory() {
  if (!confirm('Start a fresh conversation? This will clear your chat memory with the AI mentor.')) {
    return;
  }

  try {
    await api.delete('/intern/chat/history');
    const container = document.getElementById('intern-chat-messages');
    if (container) {
      container.innerHTML = `
        <div class="chat-msg ai">
          Hello! I am your InternFlow AI Mentor. Context memory has been refreshed. How can I help you accelerate your implementation today?
        </div>
      `;
    }
    showToast('Conversation history reset successfully.', 'info');
  } catch (err) {
    showToast(`Failed to clear history: ${err.message}`, 'error');
  }
}

async function handleSendInternChat(e) {
  e.preventDefault();
  const input = document.getElementById('intern-chat-input');
  const btn = document.getElementById('intern-chat-btn');
  const container = document.getElementById('intern-chat-messages');
  const message = input.value.trim();

  if (!message) return;

  // Append user message
  const userBubble = document.createElement('div');
  userBubble.className = 'chat-msg user';
  userBubble.innerText = message;
  container.appendChild(userBubble);
  input.value = '';
  container.scrollTop = container.scrollHeight;

  // Append typing indicator
  const aiBubble = document.createElement('div');
  aiBubble.className = 'chat-msg ai';
  aiBubble.innerText = 'AI Mentor is formulating response...';
  container.appendChild(aiBubble);
  container.scrollTop = container.scrollHeight;

  btn.disabled = true;

  try {
    const res = await api.post('/intern/chat', { message });
    aiBubble.innerHTML = res.reply.replace(/\n/g, '<br>');
    const badge = document.getElementById('chat-engine-badge');
    if (badge) badge.innerText = res.model || 'Local AI';
  } catch (err) {
    aiBubble.innerText = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
    container.scrollTop = container.scrollHeight;
  }
}

async function loadInternCertificate() {
  const container = document.getElementById('intern-cert-container');
  try {
    const cert = await api.get('/intern/certificate');
    container.innerHTML = '';

    if (!cert.eligible) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
          <div style="font-size: 48px; margin-bottom: 16px;">🏆</div>
          <h3 style="font-size: 18px; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">Certificate in Progress</h3>
          <p style="font-size: 13.5px; color: var(--text-muted); max-width: 520px; margin: 0 auto 20px;">
            ${cert.message}
          </p>
          <div style="max-width: 400px; margin: 0 auto;">
            <div class="progress-bar-bg" style="height: 10px;">
              <div class="progress-bar-fill" style="width: ${(cert.tasks_completed / (cert.tasks_total || 1)) * 100}%;"></div>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
              Completed: ${cert.tasks_completed} of ${cert.tasks_total} Milestones
            </div>
          </div>
        </div>
      `;
      return;
    }

    // Render formal Certificate
    container.innerHTML = `
      <div class="cert-frame">
        <div style="font-size: 14px; font-weight: 700; letter-spacing: 2px; color: var(--accent); text-transform: uppercase;">
          InternFlow AI Certification Authority
        </div>
        <h1 style="font-size: 28px; font-weight: 900; color: var(--primary); margin: 16px 0 6px;">
          CERTIFICATE OF COMPLETION
        </h1>
        <p style="font-size: 14px; color: #64748B; font-style: italic;">This is proudly presented to</p>
        <h2 style="font-size: 26px; font-weight: 800; color: var(--text-main); margin: 16px 0; border-bottom: 2px solid var(--border-color); display: inline-block; padding: 0 40px 8px;">
          ${cert.name}
        </h2>
        <p style="font-size: 14px; color: #334155; max-width: 560px; margin: 0 auto 20px; line-height: 1.6;">
          For successfully completing the intensive local engineering internship in the domain of 
          <strong>${cert.domain}</strong> with a performance grade of 
          <span style="color: var(--primary); font-weight: 700;">${cert.grade}</span>.
        </p>

        <div style="display: flex; justify-content: space-around; margin: 30px 0 20px; padding: 20px 0; border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Certificate ID</div>
            <div style="font-weight: 700; color: var(--primary);">${cert.certificate_number}</div>
          </div>
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Issue Date</div>
            <div style="font-weight: 700;">${cert.issue_date}</div>
          </div>
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Verification Hash</div>
            <div style="font-family: monospace; font-size: 12px; color: var(--text-muted);">${cert.verification_hash}</div>
          </div>
        </div>

        <div style="display: flex; justify-content: center; gap: 12px; margin-top: 10px;">
          ${cert.download_url ? `<a href="${cert.download_url}" target="_blank" class="btn btn-primary" style="text-decoration: none;">📥 Download Official PDF</a>` : ''}
          <a href="/verify/${cert.certificate_number}" target="_blank" class="btn btn-secondary" style="text-decoration: none;">🔍 Public QR Verification</a>
          <button class="btn btn-secondary" onclick="window.print()">🖨️ Print Certificate</button>
        </div>
      </div>
    `;
  } catch (err) {
    showToast(`Failed to load certificate: ${err.message}`, 'error');
  }
}
