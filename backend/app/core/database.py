from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def auto_migrate_schema():
    """Safely adds missing columns to SQLite tables if schema has evolved."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    column_patches = {
        "submissions": [
            ("version", "INTEGER DEFAULT 1"),
            ("file_type", "VARCHAR(50)"),
            ("file_size_bytes", "INTEGER"),
            ("is_latest", "BOOLEAN DEFAULT 1"),
            ("extracted_text", "TEXT")
        ],
        "evaluations": [
            ("completion_percentage", "FLOAT DEFAULT 0.0"),
            ("requirements_fulfilled", "TEXT"),
            ("missing_requirements", "TEXT"),
            ("technical_mistakes", "TEXT"),
            ("code_quality_observations", "TEXT"),
            ("step_by_step_corrections", "TEXT"),
            ("ai_model_used", "VARCHAR(100)"),
            ("is_ai_generated", "BOOLEAN DEFAULT 0"),
            ("final_status", "VARCHAR(50) DEFAULT 'approved'")
        ],
        "email_logs": [
            ("intern_id", "INTEGER"),
            ("html_body", "TEXT"),
            ("error_message", "TEXT"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("idempotency_hash", "VARCHAR(64)")
        ],
        "meetings": [
            ("google_event_id", "VARCHAR(255)"),
            ("google_meet_url", "VARCHAR(500)"),
            ("is_google_calendar_synced", "BOOLEAN DEFAULT 0")
        ],
        "automation_jobs": [
            ("intern_id", "INTEGER"),
            ("workflow_id", "VARCHAR(100)"),
            ("scheduled_at", "DATETIME"),
            ("last_attempt_at", "DATETIME"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("max_retries", "INTEGER DEFAULT 3"),
            ("error_message", "TEXT"),
            ("idempotency_key", "VARCHAR(128)")
        ],
        "interns": [
            ("workflow_status", "VARCHAR(50) DEFAULT 'active'"),
            ("workflow_paused", "BOOLEAN DEFAULT 0")
        ],
        "certificates": [
            ("file_path", "VARCHAR(500)")
        ]
    }
    
    with engine.connect() as conn:
        for table, cols in column_patches.items():
            if table in inspector.get_table_names():
                existing_cols = set(c["name"] for c in inspector.get_columns(table))
                for col_name, col_type in cols:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception as e:
                            pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

