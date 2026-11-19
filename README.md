# 🚀 InternFlow AI

**AI-Powered Intelligent Internship Management and Complete Automation Platform**

InternFlow AI is an enterprise-grade, on-premise internship management and autonomous lifecycle automation platform designed for engineering teams, universities, and enterprise organizations. It completely automates intern onboarding, Excel roster ingestion, personalized local AI roadmap synthesis, task delivery, review scheduling, sandboxed code evaluation, mentor revisions, and completion certification—running 100% locally on your laptop with **zero cloud dependencies, no AWS services, and no paid API keys**.

---

## 🌟 Key Capabilities & Architectural Pillars

### 1. 🛡️ Role-Based Access Control & Strict Data Isolation
- **Admin Portal**: Comprehensive supervisor workspace for intern rosters, Excel ingestion, AI roadmap reviews, task evaluations, automation queue controls, and audit logs.
- **Intern Portal**: Personalized workspace strictly isolated to each intern's own profile, milestones, deliverables, evaluation history, and certificate.
- **Horizontal Access Defense**: Direct database-level ownership barriers; interns cannot view, submit, or manipulate other interns' tasks, records, or chats (HTTP 403 Forbidden).
- **Secure Hashing & Tokens**: Direct bcrypt password encryption and PyJWT tokens.
- **Activation Flow**: Secure invitation token and temporary password onboarding flows.

### 2. 📊 Real-Time SQLite & SQLAlchemy Database Architecture
- Relational schema with **15 distinct tables** managed via SQLAlchemy:
  - `Admins / Users`
  - `Interns`
  - `Tasks`
  - `Weekly Roadmaps`
  - `Submissions`
  - `Evaluations`
  - `Meetings`
  - `Attendance`
  - `Email Logs` (Simulated local inbox)
  - `Notifications`
  - `Certificates`
  - `Chat History`
  - `Automation Jobs`
  - `Audit Logs`
  - `Application Settings`

### 3. 📑 Excel Ingestion & 10-Step Validation Pipeline
- **Auto-Mapping**: Intelligently detects variations in column headers (`Intern Name`, `Email Address`, `Domain`, `Main Assigned Task`, `Task Description`, `Start Date`, `Duration`, `End Date`).
- **Validation**: Strict regex email validation, missing field detection, and duplicate checks against both the uploaded file and existing SQLite database records.
- **Interactive Review & Correction**: Admin can edit and correct cells directly within the browser preview before committing.
- **Strict Approval Gate**: No accounts or automated workflows are triggered until the administrator explicitly clicks **Approve & Import**.
- **Sample Template**: One-click download of a pre-formatted Excel template (`/api/v1/excel/download-template`).

### 4. 🧠 Local AI & Ollama Integration (with Autonomous Fallback Engine)
- **Ollama Local LLM Service**: Direct connection to `http://127.0.0.1:11434` with model autodetection (`llama3`, `mistral`, `phi3`, etc.).
- **Domain-Tailored Roadmaps**: Synthesizes structured, non-generic weekly milestones matching the intern's exact domain (*AI/ML, Full Stack Web Dev, Cloud & DevOps, Cybersecurity, Data Science, Mobile*).
- **Curriculum Architecture**: Generates step-by-step instructions, recommended tech stacks, expected outputs, submission requirements, and evaluation rubrics.
- **Autonomous Fallback Engine**: If Ollama is offline or downloading models, InternFlow AI's built-in domain curriculum engine automatically takes over with zero crashes or downtime.
- **Interactive AI Mentor**: Interns have access to a contextual local AI chatbot for guidance on their assigned project with isolated conversational memory.

### 5. 📧 Gmail SMTP Integration & Reliable Automated Email System
- **13 Responsive HTML Email Templates**:
  1. Welcome Email
  2. Internship Confirmation
  3. Weekly Task Assignment
  4. Detailed Task Explanation
  5. Task Deadline Reminder
  6. Submission Reminder
  7. Review Meeting Invitation
  8. AI Evaluation Feedback
  9. Resubmission Notification
  10. Next-Week Assignment
  11. Internship Completion Email
  12. Certificate Delivery (with embedded PDF attachment)
  13. Final Appreciation Email (personalized achievements, skills, highlights, career suggestions)
- **Reliability & Idempotency**: Built-in duplicate email prevention via SHA-256 idempotency hashing, local queue, connection testing, and retry capability.
- **Accurate Delivery Tracking**: Logs exact statuses (`QUEUED`, `SMTP_ACCEPTED`, `FAILED`) without falsely claiming inbox delivery.
- **Credential Safety**: Configured via `.env` (`SMTP_SERVER=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_EMAIL`, `SMTP_PASSWORD`), never hardcoded or exposed to the client.

### 6. 📅 Google Calendar & Google Meet Integration (OAuth 2.0)
- **Genuine Google Meet Generation**: Creates authentic Hangouts/Google Meet video conferences using Google Calendar API v3 `conferenceData` with `requestId` and reminders.
- **Zero Fake URLs**: Never generates synthetic meeting links; accurately reports setup requirements if OAuth credentials are not configured.
- **Meeting Management**: Automatic sync, intern email invitations, rescheduling, and cancellation.

### 7. 📤 Secure Multi-Format Task Submission & Versioning
- **Accepted Formats**: `.zip`, `.pdf`, `.docx`, `.pptx`, source code files (`.py`, `.js`, `.ts`, `.html`, `.css`, `.sql`, `.json`, `.md`), and GitHub / hosted project URLs.
- **Safe Sandboxed Content Extraction**: Safely inspects and extracts text content using `pypdf`, `python-docx`, and text readers without executing untrusted code on the host machine.
- **Automatic Versioning**: Every resubmission increments version (`v1`, `v2`, `v3`) with full revision history and `is_latest` tracking.
- **File Validation**: Strict 25 MB size limits and blocklist preventing execution of binaries (`.exe`, `.bat`, `.sh`).

### 8. 🤖 Ollama Local AI Task Evaluation (9-Point Rubric)
- **Structured 9-Point Evaluation Rubric**: Compares submitted deliverable against original task specs, expected output, and criteria:
  1. Overall Score out of 100
  2. Completion Percentage
  3. Requirements Fulfilled
  4. Missing Requirements
  5. Technical Mistakes
  6. Code Quality Observations
  7. Improvement Suggestions
  8. Step-by-Step Corrections
  9. Final Evaluation Status (`approved` / `needs_resubmission` / `rejected`)
- **Mentor Review & Modification**: Mentors can inspect AI analysis, adjust scores and feedback, and publish.
- **Automatic Notification & Recalculation**: Automatically updates intern total score and dispatches personalized email notification.

### 9. 🔄 End-to-End Autonomous Lifecycle Engine (18 Sequential Steps)
Once the administrator approves the ingested Excel roster, InternFlow AI autonomously executes the full 18-step intern lifecycle per intern:
1. Create individual intern user account.
2. Send personalized Welcome Email.
3. Generate domain-tailored weekly roadmap.
4. Assign Week 1 tasks.
5. Send Task Assignment Email with technical instructions.
6. Calculate and persist submission deadlines.
7. Send proactive deadline reminders.
8. Automatically schedule review meetings in Google Calendar.
9. Generate genuine Google Meet video conferencing links.
10. Send Google Meet review invitations.
11. Ingest multi-format deliverables.
12. Trigger Ollama 9-point rubric AI evaluation.
13. Dispatch personalized AI feedback emails.
14. Handle resubmissions with automated version tracking (`v1` → `v2`).
15. Unlock and advance to the next milestone task upon mentor approval.
16. Generate the subsequent weekly assignment dynamically.
17. Schedule the next milestone review meeting.
18. Execute completion verification, ReportLab PDF certificate generation, and final appreciation delivery.

### 10. 🎛️ Automation Control Center & Persistent SQLite Job Engine
- **Admin Control Center**: Real-time overview of active workflows, completed workflows, pending jobs, failed jobs, and scheduled triggers.
- **Autonomous Job Execution**: Database-backed `automation_jobs` table processed by a background loop every 30 seconds.
- **Job Controls**:
  - One-click **Run Pending Jobs Now** for instant execution.
  - Manual **Retry Job** for failed actions with exponential backoff.
  - Workflow **Pause**, **Resume**, and **Cancel** controls for individual interns.
- **Laptop Restart Recovery**: Detects interrupted `running` jobs on restart and automatically resets them to `pending` with zero missed executions.
- **Idempotency Protection**: SHA-256 keys prevent duplicate email dispatch, task assignment, and meeting generation.

### 11. ⏱️ Configurable Automation Schedules
Admin can customize all scheduling parameters via the Admin Portal (`/api/v1/automation/settings`):
- **Working Days**: Select active operational days (e.g. Monday - Friday).
- **Review Day & Time**: Configurable review day (e.g. Sunday) and time (e.g. `16:00`).
- **Submission Deadlines**: Configurable deadline day offset.
- **Extension Rules**: Configurable deadline extension days on revision requests (e.g. 3 days).
- **Timezone**: Full timezone-aware scheduling.

### 12. 📜 ReportLab PDF Certificate Generation & Public QR Code Verification
- **High-Resolution Vector PDF**: Generated using ReportLab `landscape(letter)` canvas with dual navy/gold security borders, geometric corner accents, watermark rosette, clean typography, and authorized mentor signatures.
- **Embedded QR Code**: Automatically generated using `qrcode[pil]`, pointing directly to the public verification endpoint `http://localhost:8000/verify/{certificate_number}`.
- **Local Storage**: Saved securely on disk at `data/uploads/certificates/`.
- **Public Online Verification**: Public portal at `/verify` and `/verify/{certificate_number}` verifying intern name, domain, capstone project, completion term, performance grade, and SHA-256 integrity hash.
- **Direct PDF Delivery**: Automatically emailed to the intern as an attachment using Gmail SMTP.

### 13. 📈 Advanced Admin Analytics & At-Risk Intern Detection
- **At-Risk Intern Detection**: Flags interns with pending revisions, overdue submissions, or low average scores (< 60%).
- **Turnaround Analysis**: Measures average submission-to-review time in hours.
- **Performance Tiers**: Automatically categorizes interns into *Outstanding (≥85%)*, *Proficient (70-84%)*, and *Needs Support (<70%)*.
- **Weekly Milestone Rates**: Real-time completion rates per week across all domains.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| **Frontend** | HTML5, Modern CSS3 (Grid & Flexbox), Vanilla JavaScript (ES6+) |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Starlette |
| **Database** | SQLite, SQLAlchemy ORM (15 relational models) |
| **Local AI** | Ollama Local LLM (`http://localhost:11434`) + Autonomous Curriculum Fallback Engine |
| **PDF Generation** | ReportLab 5.1.0, Pillow, QRCode (with QR vector stamp) |
| **Data Processing** | Pandas, OpenPyXL, PyPDF, Python-Docx |
| **Security** | Direct Bcrypt hashing, PyJWT tokens, Python-dotenv |
| **External APIs** | Gmail SMTP (MIME multipart/mixed), Google Calendar API v3 (OAuth 2.0) |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure you have Python 3.10 or higher installed on your laptop.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Platform
Run the single unified launcher:
```bash
python run.py
```

The application will start immediately at:
- **Landing & Authentication Portal**: [http://localhost:8000](http://localhost:8000)
- **Admin Portal**: [http://localhost:8000/admin](http://localhost:8000/admin)
- **Intern Portal**: [http://localhost:8000/intern](http://localhost:8000/intern)
- **Public Certificate Verification**: [http://localhost:8000/verify](http://localhost:8000/verify)
- **Interactive API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔑 Default Credentials

### Administrator Account
- **Email**: `admin@internflow.ai`
- **Password**: `Admin@123`
*(Or click the **Admin Demo** button on the login screen to autofill credentials)*

### Sample Intern Accounts
When an Excel roster is imported and approved, each intern account is provisioned:
- **Email**: Their registered email (e.g. `ananya.deshmukh@example.com`)
- **Initial Password**: `Intern@` + last 4 digits of their Intern Code (e.g., `Intern@0014`)
- **Alternative**: Secure invitation token entered via the **Activate Invite** tab.

---

## 🧪 Comprehensive Automated Verification Suites

The system includes 3 end-to-end verification suites verifying every layer of the application:

### 1. Phase 1 Core Lifecycle Verification (12 Stages)
Verifies authentication, SQLite database operations, Excel 10-step validation, admin approval, strict data isolation, AI roadmap generation, task submission, evaluation, and dashboard analytics:
```bash
python tests/test_internflow.py
```

### 2. Phase 2 Advanced Integrations & AI Evaluation Suite (10 Stages)
Verifies Gmail SMTP reliability, duplicate email prevention, Google Calendar OAuth probes, multi-format file uploads, executable file blocking, version increments (`v1` to `v2`), Ollama 9-point rubric evaluation, mentor score editing, attendance check-ins, isolated AI mentor memory, and health monitor:
```bash
python tests/test_phase2.py
```

### 3. Phase 3 Complete Lifecycle Automation Suite (16 Stages)
Simulates a multi-intern cohort through all 18 lifecycle automation steps: Excel approval, background queue dispatches, cross-intern security barriers, version 1 delivery, Ollama 9-point evaluation, revision requests with automatic deadline extensions, version 2 approval, automatic advancement to Week 2, ReportLab PDF certificate generation, public online QR code verification, workflow pause/resume/cancel controls, configurable schedule settings, at-risk intern alerts, and laptop restart recovery:
```bash
python tests/test_phase3.py
```

---

## 📂 Project Directory Structure

```text
aws vignesh/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── deps.py               # Role validation & strict intern data isolation
│       │   └── v1/
│       │       ├── api.py            # Unified v1 router
│       │       ├── auth.py           # Login, invite activation, password reset
│       │       ├── admin.py          # Dashboard analytics, intern roster, evaluations
│       │       ├── excel.py          # Excel upload, auto-mapping, preview, approval
│       │       ├── interns.py        # Isolated intern workspace, submissions, AI chat
│       │       ├── roadmaps.py       # Roadmap generation and milestones
│       │       ├── ollama.py         # Ollama connectivity & prompt sandbox
│       │       ├── automation.py     # Control center, job execution, schedule settings
│       │       └── certificates.py   # PDF issuance, verification, public download
│       ├── core/
│       │   ├── config.py             # App settings & .env configuration
│       │   ├── database.py           # SQLite connection, session factory & auto-migrations
│       │   └── security.py           # Direct bcrypt hashing & JWT tokens
│       ├── models/                   # 15 Relational SQLAlchemy entities
│       │   ├── user.py
│       │   ├── intern.py
│       │   ├── roadmap.py
│       │   ├── task.py
│       │   ├── submission.py
│       │   ├── evaluation.py
│       │   ├── meeting.py
│       │   ├── attendance.py
│       │   ├── notification.py
│       │   ├── certificate.py
│       │   ├── chat.py
│       │   ├── log.py
│       │   └── setting.py
│       ├── schemas/                  # Pydantic request & response schemas
│       ├── services/                 # Core business logic services
│       │   ├── auth_service.py
│       │   ├── excel_service.py
│       │   ├── ollama_service.py
│       │   ├── email_service.py      # Gmail SMTP with MIME attachments & 13 templates
│       │   ├── calendar_service.py   # Google Calendar & Meet OAuth 2.0 integration
│       │   ├── submission_service.py # Secure sandboxed file extraction & versioning
│       │   ├── chat_service.py       # Isolated conversational AI intern mentor
│       │   ├── certificate_service.py# ReportLab vector PDF & QR code engine
│       │   ├── automation_service.py # 18-step autonomous lifecycle scheduler
│       │   └── analytics_service.py  # At-risk intern detection & performance tiers
│       └── main.py                   # FastAPI lifespan, background loop & static routes
├── frontend/
│   ├── index.html                    # Landing page & unified login
│   ├── verify.html                   # Public certificate online verification page
│   ├── admin/
│   │   └── index.html                # Complete Admin Portal & Automation Control Center
│   ├── intern/
│   │   └── index.html                # Complete Intern Portal & Certificate Download
│   └── static/
│       ├── css/
│       │   └── main.css              # Custom SaaS design system (#1E3A8A / #2563EB / #F97316)
│       └── js/
│           ├── api.js                # Token management & HTTP request wrapper
│           ├── admin.js              # Admin portal reactive controllers & modals
│           └── intern.js             # Intern portal deliverables & AI mentor logic
├── data/
│   ├── internflow.db                 # SQLite database
│   ├── uploads/
│   │   ├── submissions/              # Secure local deliverable storage
│   │   └── certificates/             # Generated ReportLab PDF certificates
│   └── sample_template/              # Standard Excel templates
├── tests/
│   ├── test_internflow.py            # Phase 1 verification (12 stages)
│   ├── test_phase2.py                # Phase 2 verification (10 stages)
│   └── test_phase3.py                # Phase 3 verification (16 stages)
├── run.py                            # Single 1-click launcher
├── requirements.txt
├── .env
└── README.md
```

---

## 🔒 Security & Sandboxing Guarantees
- **100% Local Execution**: All processing, SQLite databases, AI inferences, and generated files reside strictly on `127.0.0.1`.
- **Zero Cloud Leakage**: No telemetry, AWS calls, external APIs, or remote data sharing.
- **Sandboxed File Ingestion**: Uploaded code and documents are parsed safely using text stream readers and document parsers. **Untrusted code is never executed on the host machine**.
- **Role Isolation**: Submissions and profile queries strictly enforce `intern_id` matching to prevent horizontal privilege escalation.
