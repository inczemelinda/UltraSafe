ALTER TABLE template_change_suggestion_hunk
    ADD COLUMN IF NOT EXISTS template_section_title TEXT,
    ADD COLUMN IF NOT EXISTS template_article_title TEXT,
    ADD COLUMN IF NOT EXISTS before_context TEXT,
    ADD COLUMN IF NOT EXISTS after_context TEXT,
    ADD COLUMN IF NOT EXISTS full_context_excerpt TEXT,
    ADD COLUMN IF NOT EXISTS start_offset INTEGER,
    ADD COLUMN IF NOT EXISTS end_offset INTEGER;
