import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.intern import Intern
from app.models.roadmap import WeeklyRoadmap
from app.models.task import Task
from app.models.log import AuditLog, AutomationJob

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, default_model: str = settings.OLLAMA_DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def check_connection(self) -> Dict[str, Any]:
        """Checks if local Ollama daemon is running and lists pulled models."""
        try:
            with httpx.Client(timeout=2.5) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return {
                        "connected": True,
                        "base_url": self.base_url,
                        "available_models": models,
                        "active_model": models[0] if models else self.default_model,
                        "status_text": f"Ollama Active ({len(models)} models available)" if models else "Ollama Active (No models pulled yet)"
                    }
                return {
                    "connected": False,
                    "base_url": self.base_url,
                    "available_models": [],
                    "active_model": None,
                    "status_text": f"Ollama HTTP {res.status_code}. Autonomous Engine ready."
                }
        except Exception as e:
            return {
                "connected": False,
                "base_url": self.base_url,
                "available_models": [],
                "active_model": None,
                "status_text": f"Ollama Offline ({type(e).__name__}). Autonomous Engine ready."
            }

    def generate_completion(self, prompt: str, system_prompt: str = "", model: Optional[str] = None) -> Optional[str]:
        """Calls Ollama HTTP API with stream=False."""
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9
            }
        }
        try:
            with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code == 200:
                    return response.json().get("response", "")
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            return None
        return None

    def create_roadmap_for_intern(
        self,
        intern: Intern,
        db: Session,
        model_name: Optional[str] = None,
        force_regenerate: bool = False
    ) -> List[WeeklyRoadmap]:
        """Generates a complete, tailored weekly roadmap and associated tasks."""
        # If roadmaps exist and not forcing regeneration, return existing
        existing_roadmaps = db.query(WeeklyRoadmap).filter(WeeklyRoadmap.intern_id == intern.id).all()
        if existing_roadmaps and not force_regenerate:
            return existing_roadmaps

        # Delete existing if regenerating
        if existing_roadmaps and force_regenerate:
            for r in existing_roadmaps:
                db.delete(r)
            db.commit()

        # Check Ollama connection
        conn_info = self.check_connection()
        used_model = model_name or conn_info.get("active_model") or self.default_model
        generated_weeks_data: List[Dict[str, Any]] = []
        ai_engine_used = "Ollama Local LLM" if conn_info["connected"] else "Domain Curriculum Engine (Local AI Fallback)"

        if conn_info["connected"] and conn_info.get("available_models"):
            # Query Ollama
            prompt = self._build_ollama_prompt(intern)
            system = "You are an expert technical internship supervisor and curriculum architect. Return ONLY valid JSON."
            response_text = self.generate_completion(prompt, system, used_model)
            if response_text:
                parsed = self._extract_json_from_text(response_text)
                if parsed and isinstance(parsed, list):
                    generated_weeks_data = parsed

        # If Ollama didn't return valid data or is offline, use intelligent curriculum engine
        if not generated_weeks_data:
            generated_weeks_data = self._generate_intelligent_fallback_roadmap(intern)
            ai_engine_used = "Domain Curriculum Engine (Local AI Fallback)"

        # Save to SQLite Database
        saved_roadmaps: List[WeeklyRoadmap] = []

        for week_idx, week_info in enumerate(generated_weeks_data, start=1):
            week_num = week_info.get("week_number", week_idx)
            week_title = week_info.get("title", f"Week {week_num}: Core Implementation")
            theme = week_info.get("theme", f"{intern.domain} Foundations & Architecture")
            objectives = week_info.get("objectives", "Complete architectural milestones and core functionality.")
            deliverables = week_info.get("deliverables", "Source code, unit tests, and milestone report.")
            hours = week_info.get("estimated_hours", 20)

            roadmap = WeeklyRoadmap(
                intern_id=intern.id,
                week_number=week_num,
                title=week_title,
                theme=theme,
                objectives=objectives if isinstance(objectives, str) else "\n".join(objectives),
                key_deliverables=deliverables if isinstance(deliverables, str) else "\n".join(deliverables),
                estimated_hours=hours,
                ai_generated=True,
                status="approved",  # Initial active/approved state so intern can begin
                approved_by_admin=True,
                approved_at=datetime.utcnow()
            )
            db.add(roadmap)
            db.flush()

            # Create the main task for this week
            task_info = week_info.get("task", {})
            task_title = task_info.get("title", f"Milestone {week_num}: {week_title}")
            task_desc = task_info.get("description", f"Implement phase {week_num} for {intern.main_task}.")
            instructions = task_info.get("instructions", "1. Review technical specs\n2. Implement code modules\n3. Write unit tests\n4. Push to Git")
            technologies = task_info.get("technologies", self._get_default_tech_stack(str(intern.domain or "")))
            expected_output = task_info.get("expected_output", "Functional code repository with documentation and passing test suite.")
            submission_req = task_info.get("submission_requirements", "GitHub repository URL, deployed demo or video walk-through, and engineering report.")
            evaluation_crit = task_info.get("evaluation_criteria", "Architecture & Clean Code (30%), Functionality (40%), Documentation (15%), Test Coverage (15%).")

            # Deadline: end of each week from start_date
            raw_start = getattr(intern, "start_date", None)
            if isinstance(raw_start, datetime):
                s_date = raw_start.date()
            elif isinstance(raw_start, date):
                s_date = raw_start
            else:
                s_date = date.today()
            deadline_date = datetime.combine(s_date + timedelta(weeks=week_num), datetime.min.time()) + timedelta(hours=23, minutes=59)

            task = Task(
                intern_id=intern.id,
                roadmap_id=roadmap.id,
                week_number=week_num,
                title=task_title,
                description=task_desc,
                instructions=instructions if isinstance(instructions, str) else "\n".join(instructions),
                technologies=technologies if isinstance(technologies, str) else ", ".join(technologies),
                expected_output=expected_output,
                submission_requirements=submission_req,
                evaluation_criteria=evaluation_crit,
                deadline=deadline_date,
                status="pending",
                max_score=100.0
            )
            db.add(task)
            saved_roadmaps.append(roadmap)

        # Record automation job and audit log
        job = AutomationJob(
            job_type="roadmap_generation",
            status="completed",
            payload=json.dumps({"intern_id": intern.id, "domain": intern.domain, "weeks": intern.duration_weeks}),
            result=json.dumps({"engine": ai_engine_used, "weeks_generated": len(saved_roadmaps)}),
            finished_at=datetime.utcnow()
        )
        db.add(job)

        audit = AuditLog(
            user_id=None,
            action="ROADMAP_GENERATED",
            entity_type="Intern",
            entity_id=str(intern.id),
            details=f"Generated {len(saved_roadmaps)}-week roadmap using {ai_engine_used} for {intern.name}."
        )
        db.add(audit)
        db.commit()

        return saved_roadmaps

    def _build_ollama_prompt(self, intern: Intern) -> str:
        return f"""
You are an expert technical internship supervisor. Generate a structured {intern.duration_weeks}-week internship roadmap and task breakdown for an intern.

Intern Details:
- Name: {intern.name}
- Domain: {intern.domain}
- Main Assigned Task: {intern.main_task}
- Task Description: {intern.task_description or 'No extra description'}
- Duration: {intern.duration_weeks} weeks

Respond with a JSON array where each element has:
- "week_number": integer (1 to {intern.duration_weeks})
- "title": string (Week focus title)
- "theme": string
- "objectives": string
- "deliverables": string
- "estimated_hours": integer (e.g. 20)
- "task": object with:
  - "title": string
  - "description": string
  - "instructions": string (step-by-step numbered guide)
  - "technologies": string (relevant tools/libraries)
  - "expected_output": string
  - "submission_requirements": string
  - "evaluation_criteria": string
"""

    def _extract_json_from_text(self, text: str) -> Optional[Any]:
        """Extracts JSON structure from model output."""
        try:
            # Direct parse
            return json.loads(text)
        except Exception:
            pass
        # Search for array [...]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        return None

    def _get_default_tech_stack(self, domain: str) -> str:
        d = domain.lower()
        if "ai" in d or "machine learning" in d:
            return "Python 3.10+, PyTorch/TensorFlow, Hugging Face, LangChain, ChromaDB, FastAPI, Pandas, NumPy"
        elif "web" in d or "full stack" in d:
            return "HTML5, CSS3, JavaScript/TypeScript, React/Vue, Python FastAPI / Node.js, SQLite/PostgreSQL, Git"
        elif "cloud" in d or "devops" in d:
            return "Docker, Kubernetes, Linux Shell, GitHub Actions, Prometheus, Grafana, Nginx, Python"
        elif "cyber" in d or "security" in d:
            return "Python, Wireshark, OWASP ZAP, Nmap, Cryptography, Linux, Burp Suite, Bash"
        elif "data" in d:
            return "Python, Pandas, SQL, Scikit-Learn, Matplotlib, Seaborn, PowerBI/Streamlit"
        elif "mobile" in d:
            return "Flutter / React Native, Dart / TypeScript, REST APIs, SQLite / Firebase"
        return "Python, Git, Modern Web Stack, Automated Testing Tools"

    def _generate_intelligent_fallback_roadmap(self, intern: Intern) -> List[Dict[str, Any]]:
        """Intelligent, domain-tailored curriculum engine providing production-grade roadmaps."""
        domain_lower = intern.domain.lower()
        proj = intern.main_task
        weeks_total = intern.duration_weeks

        # Determine domain archetype
        if "ai" in domain_lower or "machine learning" in domain_lower or "deep learning" in domain_lower:
            archetype = "ai_ml"
        elif "web" in domain_lower or "full stack" in domain_lower or "frontend" in domain_lower or "backend" in domain_lower:
            archetype = "web_dev"
        elif "cloud" in domain_lower or "devops" in domain_lower or "infrastructure" in domain_lower:
            archetype = "devops"
        elif "cyber" in domain_lower or "security" in domain_lower:
            archetype = "security"
        elif "data" in domain_lower:
            archetype = "data_science"
        else:
            archetype = "software_eng"

        weeks: List[Dict[str, Any]] = []

        curriculums: Dict[str, List[Dict[str, Any]]] = {
            "ai_ml": [
                {
                    "title": "Architecture Design & Environment Setup",
                    "theme": "Problem Formulation & Data Pipeline Pipeline",
                    "objectives": f"Set up Python virtual environment, inspect datasets, establish baseline metrics for '{proj}'.",
                    "deliverables": "Repository structure, EDA Jupyter notebook, data cleaning script, baseline model evaluation.",
                    "task": {
                        "title": f"Phase 1: Problem Formulation & Data Pipeline for {proj}",
                        "description": f"Architect the machine learning solution for '{proj}'. Ingest raw data, perform exploratory data analysis, and establish benchmark performance metrics.",
                        "instructions": "1. Initialize Git repository with README and requirements.txt.\n2. Implement robust data ingestion and validation with Pandas/NumPy.\n3. Conduct Exploratory Data Analysis (EDA) with visualizations.\n4. Train a baseline benchmark model and record loss/accuracy curves.\n5. Document baseline findings in a markdown report.",
                        "technologies": "Python 3.10+, Pandas, NumPy, Scikit-Learn, Matplotlib, Git",
                        "expected_output": "Clean repository containing data pipeline scripts, reproducible EDA notebook, and baseline metrics log.",
                        "submission_requirements": "GitHub repo URL, PDF summary of EDA findings, and execution instructions.",
                        "evaluation_criteria": "Code cleanliness (30%), Data validation completeness (30%), Benchmark documentation (20%), Commit quality (20%)."
                    }
                },
                {
                    "title": "Model Development & Feature Engineering",
                    "theme": "Advanced Modeling & Feature Extraction",
                    "objectives": f"Engineer domain-specific features and train modern deep learning / ML models for '{proj}'.",
                    "deliverables": "Feature transformation pipeline, training scripts, cross-validation report, hyperparameter tuning logs.",
                    "task": {
                        "title": f"Phase 2: Core Algorithm Development & Optimization for {proj}",
                        "description": "Develop the core machine learning algorithm. Implement feature extraction, train neural architectures or ensemble models, and run hyperparameter tuning.",
                        "instructions": "1. Build modular feature engineering pipeline.\n2. Implement primary model architecture (Transformers / Gradient Boosting / Neural Net).\n3. Set up K-fold cross-validation to prevent overfitting.\n4. Execute hyperparameter optimization using Optuna or GridSearch.\n5. Compare primary model metrics against Phase 1 benchmark.",
                        "technologies": "PyTorch / TensorFlow / Scikit-Learn, Optuna, Seaborn, TensorBoard",
                        "expected_output": "Modular model training package with saved checkpoint weights and performance comparison charts.",
                        "submission_requirements": "Pull request with model artifacts, validation report, and confusion matrix / ROC curves.",
                        "evaluation_criteria": "Model accuracy & generalization (40%), Code modularity (30%), Tuning rigor (20%), Documentation (10%)."
                    }
                },
                {
                    "title": "API Serving & Inference Optimization",
                    "theme": "Inference Engineering & Microservice Wrapping",
                    "objectives": f"Wrap '{proj}' into high-performance REST API endpoints with latency optimization.",
                    "deliverables": "FastAPI inference service, Pydantic validation schemas, batch inference worker, Dockerfile.",
                    "task": {
                        "title": f"Phase 3: Production API Serving for {proj}",
                        "description": "Convert the trained model into a production-ready asynchronous API microservice with input sanitization and response caching.",
                        "instructions": "1. Build FastAPI application with `/predict`, `/batch_predict`, and `/health` endpoints.\n2. Implement strict Pydantic schemas for input request validation.\n3. Optimize inference latency via ONNX runtime or model quantization.\n4. Containerize application with multi-stage Dockerfile.\n5. Write automated pytest integration tests for all endpoints.",
                        "technologies": "FastAPI, Uvicorn, Pydantic, ONNX / PyTorch, Docker, Pytest",
                        "expected_output": "Containerized REST API capable of serving real-time predictions under 150ms latency with automated tests.",
                        "submission_requirements": "Docker container build verification, API documentation (Swagger), and Postman test collection.",
                        "evaluation_criteria": "API reliability & error handling (35%), Serving throughput & latency (30%), Test coverage (20%), Container security (15%)."
                    }
                },
                {
                    "title": "Final System Integration, UI & Deployment",
                    "theme": "Full-Stack Deployment & Project Presentation",
                    "objectives": f"Complete frontend integration for '{proj}', deploy locally, and present comprehensive engineering report.",
                    "deliverables": "Interactive demo UI (Streamlit/Web), automated evaluation pipeline, final technical documentation and slide deck.",
                    "task": {
                        "title": f"Phase 4: End-to-End System Integration & Capstone Delivery for {proj}",
                        "description": f"Finalize end-to-end integration of '{proj}'. Connect the inference backend to an interactive UI, package all deliverables, and conduct a final demo.",
                        "instructions": "1. Create an intuitive user interface for uploading inputs and viewing model predictions.\n2. Connect frontend seamlessly to the FastAPI inference engine.\n3. Implement system monitoring and error logging.\n4. Complete comprehensive README with architecture diagram and setup guide.\n5. Prepare a 10-slide capstone demonstration presentation.",
                        "technologies": "Streamlit / Modern Web, FastAPI, Docker, Mermaid Diagrams, Markdown",
                        "expected_output": "End-to-end operational software product ready for stakeholder demonstration with complete documentation.",
                        "submission_requirements": "Complete Git repository link, live demo walkthrough video / screenshots, and final capstone technical report.",
                        "evaluation_criteria": "Overall solution completeness (40%), User experience (25%), Architectural robustness (20%), Final presentation quality (15%)."
                    }
                }
            ],
            "web_dev": [
                {
                    "title": "Architecture, Database Schema & Authentication",
                    "theme": "Foundations & Security Layer",
                    "objectives": f"Design relational database schema and secure authentication system for '{proj}'.",
                    "deliverables": "ER diagram, SQLAlchemy models, JWT authentication endpoints, migrations, and test suite.",
                    "task": {
                        "title": f"Phase 1: Architecture & Auth System for {proj}",
                        "description": f"Lay down the technical foundation for '{proj}'. Design relational entities, configure SQLite/PostgreSQL, and build secure JWT authentication with password hashing.",
                        "instructions": "1. Design entity-relationship diagram covering all project entities.\n2. Implement SQLAlchemy declarative models with proper indexes and foreign keys.\n3. Create secure registration, login, and password hashing using bcrypt.\n4. Implement JWT access tokens and role-based endpoint protection.\n5. Write unit tests verifying auth flows and token expiry.",
                        "technologies": "Python, FastAPI, SQLAlchemy, SQLite, bcrypt, PyJWT, Pytest",
                        "expected_output": "Operational backend engine with database tables, auth routes, and interactive Swagger documentation.",
                        "submission_requirements": "GitHub repository URL, ER diagram image, and export of passing test suite.",
                        "evaluation_criteria": "Database normalization (30%), Security implementation (35%), Code structure (20%), Unit tests (15%)."
                    }
                },
                {
                    "title": "Core Business Logic & RESTful APIs",
                    "theme": "Domain Services & Data Operations",
                    "objectives": f"Develop full CRUD operations and domain workflows for '{proj}'.",
                    "deliverables": "RESTful endpoints, data validation schemas, error handlers, and business logic services.",
                    "task": {
                        "title": f"Phase 2: Core REST APIs & Service Layer for {proj}",
                        "description": f"Build out the core business services for '{proj}'. Implement robust endpoints with filtering, sorting, pagination, and transactional integrity.",
                        "instructions": "1. Develop CRUD endpoints for all primary business resources.\n2. Implement Pydantic request and response schemas with strict validation.\n3. Add query pagination, filtering, and search functionality.\n4. Implement standardized error responses and audit logging.\n5. Build comprehensive test cases covering edge cases.",
                        "technologies": "FastAPI, SQLAlchemy, Pydantic, SQLite, Pytest",
                        "expected_output": "Complete REST API suite covering all primary features of the project with Swagger documentation.",
                        "submission_requirements": "Git commits with route implementations, API test run logs, and Swagger JSON.",
                        "evaluation_criteria": "API design consistency (30%), Business logic correctness (35%), Validation rigor (20%), Test coverage (15%)."
                    }
                },
                {
                    "title": "Responsive Frontend & State Management",
                    "theme": "User Interface & Experience",
                    "objectives": f"Construct sleek, responsive web interface for '{proj}' connected to the backend.",
                    "deliverables": "Responsive dashboard, client-side API layer, interactive forms, and notification system.",
                    "task": {
                        "title": f"Phase 3: Responsive Frontend Implementation for {proj}",
                        "description": f"Develop modern, responsive user interface for '{proj}'. Connect frontend views to backend APIs with seamless asynchronous data fetching and error states.",
                        "instructions": "1. Build responsive layouts conforming to SaaS design standards (#1E3A8A / #2563EB theme).\n2. Create reusable component cards, data tables, and modal dialogs.\n3. Implement async client service layer with JWT Authorization header injection.\n4. Add real-time user feedback, loading spinners, and toast notifications.\n5. Ensure cross-device mobile responsiveness.",
                        "technologies": "HTML5, Modern CSS3 (Grid/Flexbox), JavaScript (ES6+), Fetch API",
                        "expected_output": "Fully responsive and interactive frontend application connected to the backend without dummy mockups.",
                        "submission_requirements": "Pull request with frontend code, screenshots across desktop and mobile, and manual test report.",
                        "evaluation_criteria": "UI/UX polish (35%), Responsiveness (25%), Frontend-Backend integration (25%), Code maintainability (15%)."
                    }
                },
                {
                    "title": "Testing, Optimization & Production Polish",
                    "theme": "Quality Assurance & Capstone Deployment",
                    "objectives": f"Perform end-to-end testing, security hardening, performance tuning, and project delivery for '{proj}'.",
                    "deliverables": "E2E test suite, Lighthouse audit report, deployment script, user manual, and final demo.",
                    "task": {
                        "title": f"Phase 4: QA, Security Hardening & Capstone Delivery for {proj}",
                        "description": f"Complete end-to-end validation for '{proj}'. Resolve edge case bugs, optimize database queries, harden security headers, and present final deliverables.",
                        "instructions": "1. Perform cross-browser and end-to-end integration testing.\n2. Optimize database queries with indexes and prevent N+1 query overhead.\n3. Add CORS policies and input sanitization to prevent XSS/SQL injection.\n4. Package application with local one-click startup script (run.py).\n5. Write thorough user manual and record capstone presentation video.",
                        "technologies": "FastAPI, SQLite, Pytest, Chrome DevTools, Markdown",
                        "expected_output": "Production-grade full stack application ready for local demonstration with zero console errors.",
                        "submission_requirements": "Complete repository link, test execution video, user manual PDF, and capstone presentation slides.",
                        "evaluation_criteria": "System reliability & performance (35%), Code quality (30%), Documentation completeness (20%), Presentation (15%)."
                    }
                }
            ],
            "devops": [
                {
                    "title": "Containerization & Environment Standardization",
                    "theme": "Docker & Multi-Stage Builds",
                    "objectives": f"Containerize '{proj}' microservices with lightweight, secure Docker images.",
                    "deliverables": "Multi-stage Dockerfiles, Docker Compose environment, health checks, and security scan.",
                    "task": {
                        "title": f"Phase 1: Container Architecture for {proj}",
                        "description": f"Create reproducible container definitions for '{proj}'. Implement multi-stage builds and compose files for multi-service local orchestration.",
                        "instructions": "1. Write optimized multi-stage Dockerfiles minimizing image footprint.\n2. Configure docker-compose.yml orchestrating application, database, and cache.\n3. Implement container health checks and non-root execution users.\n4. Scan images for vulnerabilities using Trivy or Docker Scout.\n5. Document container launch instructions in README.",
                        "technologies": "Docker, Docker Compose, Linux, Shell Scripting, Trivy",
                        "expected_output": "Self-healing containerized environment that launches with a single command.",
                        "submission_requirements": "GitHub repo with Docker configuration, vulnerability scan report, and run logs.",
                        "evaluation_criteria": "Image optimization (35%), Security compliance (30%), Reproducibility (20%), Documentation (15%)."
                    }
                },
                {
                    "title": "CI/CD Pipeline Automation",
                    "theme": "Automated Testing, Linting & Build Verification",
                    "objectives": f"Build automated pipeline validating pull requests and builds for '{proj}'.",
                    "deliverables": "GitHub Actions workflow, automated linting, pytest runner, automated container publishing.",
                    "task": {
                        "title": f"Phase 2: Automated CI/CD Workflows for {proj}",
                        "description": "Implement automated Continuous Integration and Continuous Deployment workflows verifying every code change against quality gates.",
                        "instructions": "1. Create GitHub Actions workflows for continuous integration.\n2. Configure automated linters (flake8/black/eslint) and unit test runners.\n3. Add coverage thresholds (minimum 80% test coverage).\n4. Build and push container images to local or container registry on passing tests.\n5. Implement branch protection rules and status badge.",
                        "technologies": "GitHub Actions, YAML, Pytest, Flake8, Docker Registry",
                        "expected_output": "Active CI/CD pipeline that blocks regressions and automates artifact packaging.",
                        "submission_requirements": "Workflow YAML files, pipeline run history link, and test coverage badge.",
                        "evaluation_criteria": "Pipeline efficiency (35%), Test automation coverage (30%), Error handling (20%), Best practices (15%)."
                    }
                },
                {
                    "title": "Observability: Metrics, Logging & Tracing",
                    "theme": "Monitoring & System Health",
                    "objectives": f"Instrument '{proj}' with real-time metrics collection, centralized logging, and dashboards.",
                    "deliverables": "Prometheus metrics endpoint, Grafana dashboard, structured JSON logs, and alert rules.",
                    "task": {
                        "title": f"Phase 3: Observability & Health Monitoring for {proj}",
                        "description": f"Integrate telemetry into '{proj}'. Expose application metrics, aggregate error logs, and configure Grafana alerting dashboards.",
                        "instructions": "1. Instrument application with Prometheus client metrics (request count, latency, memory).\n2. Set up Prometheus scraper and Grafana service.\n3. Design Grafana dashboard showing CPU, memory, API latency percentiles.\n4. Configure structured JSON logging with correlation IDs.\n5. Establish automated alert rules for error rates > 5%.",
                        "technologies": "Prometheus, Grafana, Python Prometheus Client, Loguru, Docker",
                        "expected_output": "Real-time dashboard displaying system vitals and operational health.",
                        "submission_requirements": "Grafana dashboard JSON export, screenshot of live metrics under load, and logging setup guide.",
                        "evaluation_criteria": "Telemetry depth (35%), Dashboard design (30%), Alert definition clarity (20%), Documentation (15%)."
                    }
                },
                {
                    "title": "Production Hardening, Disaster Recovery & Capstone",
                    "theme": "Resilience, Backups & Final Presentation",
                    "objectives": f"Harden infrastructure, establish automated database backups, and present capstone for '{proj}'.",
                    "deliverables": "Automated backup cron script, disaster recovery test, security audit, and capstone presentation.",
                    "task": {
                        "title": f"Phase 4: Resilience Engineering & Capstone Delivery for {proj}",
                        "description": "Conduct security audit, simulate failover recovery, automate persistent data backups, and deliver final DevOps capstone.",
                        "instructions": "1. Implement automated database backup and restore validation script.\n2. Perform load testing using Locust or Apache Benchmark to identify bottlenecks.\n3. Harden network rules, environment secret isolation, and SSL/TLS headers.\n4. Document disaster recovery runbook.\n5. Present capstone demonstration to mentors.",
                        "technologies": "Locust, Bash, OpenSSL, Docker, Markdown",
                        "expected_output": "Resilient, load-tested system with automated backup verification and recovery runbook.",
                        "submission_requirements": "Load test report, disaster recovery runbook PDF, backup script, and presentation deck.",
                        "evaluation_criteria": "System resilience (40%), Performance under load (30%), Runbook thoroughness (20%), Presentation (10%)."
                    }
                }
            ]
        }

        # Select curriculum template or fallback to web_dev/ai_ml
        template = curriculums.get(archetype, curriculums["web_dev"])

        # Dynamically scale to intern.duration_weeks
        for w_idx in range(1, weeks_total + 1):
            t_idx = (w_idx - 1) % len(template)
            base_week = template[t_idx]
            
            w_title = f"Week {w_idx}: {base_week['title']}"
            if w_idx > len(template):
                w_title += f" (Advanced Milestone Part {w_idx // len(template) + 1})"

            week_data = {
                "week_number": w_idx,
                "title": w_title,
                "theme": base_week["theme"],
                "objectives": base_week["objectives"],
                "deliverables": base_week["deliverables"],
                "estimated_hours": 20,
                "task": {
                    "title": f"Week {w_idx}: {base_week['task']['title']}",
                    "description": base_week["task"]["description"],
                    "instructions": base_week["task"]["instructions"],
                    "technologies": base_week["task"]["technologies"],
                    "expected_output": base_week["task"]["expected_output"],
                    "submission_requirements": base_week["task"]["submission_requirements"],
                    "evaluation_criteria": base_week["task"]["evaluation_criteria"]
                }
            }
            weeks.append(week_data)

        return weeks

ollama_service = OllamaService()

