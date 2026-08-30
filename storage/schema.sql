PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    research_target TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_path TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    text TEXT NOT NULL,
    support_count INTEGER NOT NULL DEFAULT 1 CHECK (support_count >= 1),
    sentiment TEXT,
    information_level TEXT,
    source_url TEXT,
    include_in_dashboard INTEGER CHECK (
        include_in_dashboard IN (0, 1) OR include_in_dashboard IS NULL
    ),
    merged_record_ids_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT,
    UNIQUE (event_id, record_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS categories (
    event_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    category_name TEXT,
    definition TEXT,
    summary TEXT,
    raw_json TEXT,
    PRIMARY KEY (event_id, category_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comment_categories (
    event_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    sentiment TEXT,
    raw_json TEXT,
    PRIMARY KEY (event_id, record_id, category_id),
    FOREIGN KEY (event_id, record_id)
        REFERENCES comments(event_id, record_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id, category_id)
        REFERENCES categories(event_id, category_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    analysis_mode TEXT NOT NULL CHECK (analysis_mode IN ('single', 'dual')),
    final_summary_json TEXT,
    final_analysis_path TEXT,
    final_summary_path TEXT,
    semantic_analysis_path TEXT,
    classification_plan_path TEXT,
    dashboard_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS personas (
    persona_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    persona_type TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    persona_json TEXT NOT NULL,
    skill_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS persona_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL CHECK (
        evidence_role IN ('anchor', 'support', 'context')
    ),
    feature TEXT,
    confidence REAL CHECK (
        confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL
    ),
    notes TEXT,
    FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id, record_id)
        REFERENCES comments(event_id, record_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS simulations (
    simulation_id TEXT PRIMARY KEY,
    persona_id TEXT NOT NULL,
    event_id TEXT,
    scenario_id TEXT,
    scenario_text TEXT NOT NULL,
    model TEXT,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_comments_event_id
    ON comments(event_id);
CREATE INDEX IF NOT EXISTS idx_comments_platform
    ON comments(platform);
CREATE INDEX IF NOT EXISTS idx_comments_sentiment
    ON comments(sentiment);
CREATE INDEX IF NOT EXISTS idx_comment_categories_event_category
    ON comment_categories(event_id, category_id);
CREATE INDEX IF NOT EXISTS idx_persona_evidence_persona
    ON persona_evidence(persona_id);
CREATE INDEX IF NOT EXISTS idx_persona_evidence_event_record
    ON persona_evidence(event_id, record_id);
CREATE INDEX IF NOT EXISTS idx_simulations_persona
    ON simulations(persona_id);
CREATE INDEX IF NOT EXISTS idx_simulations_event
    ON simulations(event_id);

CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    text,
    content = 'comments',
    content_rowid = 'id',
    tokenize = 'trigram'
);

CREATE TRIGGER IF NOT EXISTS comments_fts_after_insert
AFTER INSERT ON comments BEGIN
    INSERT INTO comments_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS comments_fts_after_delete
AFTER DELETE ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, text)
    VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS comments_fts_after_update
AFTER UPDATE OF text ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, text)
    VALUES ('delete', old.id, old.text);
    INSERT INTO comments_fts(rowid, text) VALUES (new.id, new.text);
END;

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
