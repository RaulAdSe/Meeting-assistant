-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Speakers table
CREATE TABLE IF NOT EXISTS speakers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(external_id)
);

-- Speaker embeddings table
CREATE TABLE IF NOT EXISTS speaker_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    speaker_id UUID NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    embedding BYTEA NOT NULL, -- Store numpy array as binary
    audio_file VARCHAR(512) NOT NULL,
    segment_start FLOAT NOT NULL,
    segment_end FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT valid_segment CHECK (segment_end > segment_start)
);

-- Index for faster speaker lookups
CREATE INDEX IF NOT EXISTS idx_speaker_embeddings_speaker_id 
ON speaker_embeddings(speaker_id);

-- Index for finding embeddings by audio file
CREATE INDEX IF NOT EXISTS idx_speaker_embeddings_audio_file 
ON speaker_embeddings(audio_file);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_speakers_updated_at
    BEFORE UPDATE ON speakers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE speaker_embeddings 
ADD CONSTRAINT fk_speaker
FOREIGN KEY (speaker_id) 
REFERENCES speakers(id)
ON DELETE CASCADE;

ALTER TABLE speakers ADD CONSTRAINT unique_external_id UNIQUE (external_id);