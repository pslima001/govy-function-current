-- Schema dump govy_legal (7 tables)
-- Date: 2026-02-25

-- Table: _migration_history (4 columns)
CREATE TABLE IF NOT EXISTS _migration_history (
  id integer DEFAULT nextval('_migration_history_id_seq'::regclass) NOT NULL,
  filename character varying(200) NOT NULL,
  checksum character varying(64) NOT NULL,
  applied_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX _migration_history_pkey ON public._migration_history USING btree (id);
CREATE UNIQUE INDEX _migration_history_filename_key ON public._migration_history USING btree (filename);

-- Table: jurisdiction (5 columns)
CREATE TABLE IF NOT EXISTS jurisdiction (
  jurisdiction_id character varying(20) NOT NULL,
  name character varying(120) NOT NULL,
  uf character varying(2),
  level character varying(20) NOT NULL,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX jurisdiction_pkey ON public.jurisdiction USING btree (jurisdiction_id);

-- Table: legal_chunk (10 columns)
CREATE TABLE IF NOT EXISTS legal_chunk (
  chunk_id character varying(120) NOT NULL,
  doc_id character varying(120) NOT NULL,
  provision_key character varying(80) NOT NULL,
  order_in_doc integer DEFAULT 0 NOT NULL,
  content text NOT NULL,
  content_hash character varying(64) NOT NULL,
  char_count integer NOT NULL,
  citation_short character varying(200),
  hierarchy_path ARRAY,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX legal_chunk_pkey ON public.legal_chunk USING btree (chunk_id);
CREATE INDEX idx_chunk_doc ON public.legal_chunk USING btree (doc_id);
CREATE INDEX idx_chunk_provision ON public.legal_chunk USING btree (doc_id, provision_key);
CREATE INDEX idx_chunk_hash ON public.legal_chunk USING btree (content_hash);

-- Table: legal_document (20 columns)
CREATE TABLE IF NOT EXISTS legal_document (
  doc_id character varying(120) NOT NULL,
  jurisdiction_id character varying(20) NOT NULL,
  doc_type character varying(40) NOT NULL,
  number character varying(40),
  year smallint,
  title text NOT NULL,
  source_blob_path text,
  source_format character varying(10) DEFAULT 'pdf'::character varying NOT NULL,
  text_sha256 character varying(64),
  char_count integer,
  provision_count integer DEFAULT 0,
  chunk_count integer DEFAULT 0,
  status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
  error_message text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  updated_at timestamp with time zone DEFAULT now() NOT NULL,
  published_at date,
  effective_from date,
  effective_to date,
  status_vigencia character varying(30) DEFAULT 'desconhecido'::character varying
);

CREATE UNIQUE INDEX legal_document_pkey ON public.legal_document USING btree (doc_id);
CREATE INDEX idx_legal_doc_jurisdiction ON public.legal_document USING btree (jurisdiction_id);
CREATE INDEX idx_legal_doc_type ON public.legal_document USING btree (doc_type);
CREATE INDEX idx_legal_doc_status ON public.legal_document USING btree (status);
CREATE INDEX idx_legal_doc_vigencia ON public.legal_document USING btree (status_vigencia);
CREATE INDEX idx_legal_doc_effective ON public.legal_document USING btree (effective_from, effective_to);

-- Table: legal_provision (12 columns)
CREATE TABLE IF NOT EXISTS legal_provision (
  provision_id integer DEFAULT nextval('legal_provision_provision_id_seq'::regclass) NOT NULL,
  doc_id character varying(120) NOT NULL,
  provision_key character varying(80) NOT NULL,
  label character varying(120) NOT NULL,
  provision_type character varying(30) NOT NULL,
  parent_key character varying(80),
  hierarchy_path ARRAY,
  order_in_doc integer DEFAULT 0 NOT NULL,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  valid_from date,
  valid_to date,
  status_vigencia character varying(30) DEFAULT 'vigente'::character varying
);

CREATE UNIQUE INDEX legal_provision_pkey ON public.legal_provision USING btree (provision_id);
CREATE UNIQUE INDEX legal_provision_doc_id_provision_key_key ON public.legal_provision USING btree (doc_id, provision_key);
CREATE INDEX idx_provision_doc ON public.legal_provision USING btree (doc_id);
CREATE INDEX idx_provision_type ON public.legal_provision USING btree (provision_type);
CREATE INDEX idx_provision_parent ON public.legal_provision USING btree (doc_id, parent_key);

-- Table: legal_relation (13 columns)
CREATE TABLE IF NOT EXISTS legal_relation (
  relation_id integer DEFAULT nextval('legal_relation_relation_id_seq'::regclass) NOT NULL,
  source_doc_id character varying(120) NOT NULL,
  target_doc_id character varying(120),
  target_ref text,
  relation_type character varying(30) NOT NULL,
  source_provision character varying(80),
  notes text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  confidence character varying(10) DEFAULT 'low'::character varying,
  needs_review boolean DEFAULT true,
  evidence_text text,
  evidence_pattern character varying(200),
  evidence_position integer
);

CREATE UNIQUE INDEX legal_relation_pkey ON public.legal_relation USING btree (relation_id);
CREATE UNIQUE INDEX legal_relation_source_doc_id_target_doc_id_relation_type_so_key ON public.legal_relation USING btree (source_doc_id, target_doc_id, relation_type, source_provision);
CREATE INDEX idx_relation_source ON public.legal_relation USING btree (source_doc_id);
CREATE INDEX idx_relation_target ON public.legal_relation USING btree (target_doc_id);
CREATE INDEX idx_relation_confidence ON public.legal_relation USING btree (confidence, needs_review);

-- Table: legal_source (17 columns)
CREATE TABLE IF NOT EXISTS legal_source (
  doc_id character varying(120) NOT NULL,
  kind character varying(40) NOT NULL,
  jurisdiction character varying(20) DEFAULT 'federal/BR'::character varying NOT NULL,
  source_url text NOT NULL,
  list_url text,
  caption_raw text,
  status_hint character varying(20) DEFAULT 'vigente'::character varying NOT NULL,
  fingerprint character varying(64),
  etag text,
  last_modified text,
  ingest_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
  error_message text,
  last_checked_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  updated_at timestamp with time zone DEFAULT now() NOT NULL,
  last_success_at timestamp with time zone,
  last_error_reason text
);

CREATE UNIQUE INDEX legal_source_pkey ON public.legal_source USING btree (doc_id);
CREATE INDEX idx_source_kind ON public.legal_source USING btree (kind);
CREATE INDEX idx_source_status ON public.legal_source USING btree (ingest_status);
CREATE INDEX idx_source_hint ON public.legal_source USING btree (status_hint);

-- Row counts:
-- _migration_history: 8 rows
-- jurisdiction: 28 rows
-- legal_chunk: 6243 rows
-- legal_document: 504 rows
-- legal_provision: 16322 rows
-- legal_relation: 474 rows
-- legal_source: 502 rows

-- DONE
