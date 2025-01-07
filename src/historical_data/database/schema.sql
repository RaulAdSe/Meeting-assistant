-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS update_locations_timestamp ON locations;
DROP TRIGGER IF EXISTS update_visits_timestamp ON visits;
DROP TRIGGER IF EXISTS update_problems_timestamp ON problems;
DROP TRIGGER IF EXISTS update_solutions_timestamp ON solutions;
DROP TRIGGER IF EXISTS update_chronogram_timestamp ON chronogram_entries;
DROP TRIGGER IF EXISTS update_checklist_templates_timestamp ON checklist_templates;
DROP TRIGGER IF EXISTS update_visit_checklists_timestamp ON visit_checklists;

-- Drop existing function
DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;

-- Locations table (must be created before visits)
CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    address TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Visits table to store basic visit information
CREATE TABLE IF NOT EXISTS visits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date TIMESTAMP NOT NULL,
    location_id UUID NOT NULL REFERENCES locations(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Problems identified during visits
CREATE TABLE IF NOT EXISTS problems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    visit_id UUID NOT NULL REFERENCES visits(id),
    description TEXT NOT NULL,
    severity VARCHAR(50) NOT NULL,
    area VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'identified',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT valid_status CHECK (status IN ('identified', 'in_progress', 'resolved', 'monitoring'))
);

-- Solutions or actions taken for problems
CREATE TABLE IF NOT EXISTS solutions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID NOT NULL REFERENCES problems(id),
    description TEXT NOT NULL,
    implemented_at TIMESTAMP,
    effectiveness_rating INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_rating CHECK (effectiveness_rating BETWEEN 1 AND 5)
);

-- Chronogram entries for tracking timing
CREATE TABLE IF NOT EXISTS chronogram_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    visit_id UUID NOT NULL REFERENCES visits(id),
    task_name VARCHAR(255) NOT NULL,
    planned_start TIMESTAMP NOT NULL,
    planned_end TIMESTAMP NOT NULL,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'planned',
    dependencies UUID[] DEFAULT ARRAY[]::UUID[],
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_chronogram_status CHECK (status IN ('planned', 'in_progress', 'completed', 'delayed', 'cancelled'))
);

-- Checklist templates
CREATE TABLE IF NOT EXISTS checklist_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    items JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Checklist instances for specific visits
CREATE TABLE IF NOT EXISTS visit_checklists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    visit_id UUID NOT NULL REFERENCES visits(id),
    template_id UUID NOT NULL REFERENCES checklist_templates(id),
    completed_items JSONB DEFAULT '[]'::jsonb,
    completion_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_completion_status CHECK (completion_status IN ('pending', 'in_progress', 'completed'))
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(date);
CREATE INDEX IF NOT EXISTS idx_visits_location ON visits(location_id);
CREATE INDEX IF NOT EXISTS idx_problems_visit_id ON problems(visit_id);
CREATE INDEX IF NOT EXISTS idx_solutions_problem_id ON solutions(problem_id);
CREATE INDEX IF NOT EXISTS idx_chronogram_visit_id ON chronogram_entries(visit_id);
CREATE INDEX IF NOT EXISTS idx_visit_checklists_visit_id ON visit_checklists(visit_id);

-- Create update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $BODY$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$BODY$ language 'plpgsql';

-- Create triggers
CREATE TRIGGER update_locations_timestamp 
    BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visits_timestamp 
    BEFORE UPDATE ON visits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_problems_timestamp 
    BEFORE UPDATE ON problems
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_solutions_timestamp 
    BEFORE UPDATE ON solutions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chronogram_timestamp 
    BEFORE UPDATE ON chronogram_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_checklist_templates_timestamp 
    BEFORE UPDATE ON checklist_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visit_checklists_timestamp 
    BEFORE UPDATE ON visit_checklists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();