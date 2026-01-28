-- Migration: Add research connector types to PostgreSQL enum
-- Run this on your Render PostgreSQL database

-- Add new enum values to connectortype
ALTER TYPE connectortype ADD VALUE IF NOT EXISTS 'pubmed';
ALTER TYPE connectortype ADD VALUE IF NOT EXISTS 'researchgate';
ALTER TYPE connectortype ADD VALUE IF NOT EXISTS 'googlescholar';

-- Verify the enum values
-- SELECT unnest(enum_range(NULL::connectortype));
