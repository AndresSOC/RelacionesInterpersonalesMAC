CREATE TABLE IF NOT EXISTS fetch_sessions (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    area_config JSONB NOT NULL,
    total_cells INT DEFAULT 0,
    cells_completed INT DEFAULT 0,
    places_fetched INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS coverage_cells (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES fetch_sessions(id),
    lat DECIMAL(10,8) NOT NULL,
    lon DECIMAL(11,8) NOT NULL,
    radius_m INT NOT NULL DEFAULT 1000,
    max_pages INT NOT NULL DEFAULT 3,
    status VARCHAR(20) DEFAULT 'pending',
    places_found INT DEFAULT 0,
    api_calls INT DEFAULT 0,
    error_message TEXT,
    fetched_at TIMESTAMP,
    UNIQUE (lat, lon)
);

CREATE TABLE IF NOT EXISTS places (
    place_id VARCHAR(255) PRIMARY KEY,
    business_name VARCHAR(255),
    types TEXT,
    rating DECIMAL(3,2),
    user_ratings_total INT,
    price_level INT,
    vicinity VARCHAR(500),
    latitud DECIMAL(10,8),
    longitud DECIMAL(11,8),
    business_status VARCHAR(50),
    raw_data JSONB,
    fetched_at TIMESTAMP DEFAULT NOW(),
    cell_id INT REFERENCES coverage_cells(id),
    cluster_espacial INTEGER,
    id_colonia INTEGER
);

CREATE TABLE IF NOT EXISTS place_categories (
    place_id VARCHAR(255) REFERENCES places(place_id) ON DELETE CASCADE,
    category VARCHAR(100),
    PRIMARY KEY (place_id, category)
);

CREATE INDEX IF NOT EXISTS idx_places_latlon ON places(latitud, longitud);
CREATE INDEX IF NOT EXISTS idx_places_rating ON places(user_ratings_total DESC);
CREATE INDEX IF NOT EXISTS idx_coverage_cells_status ON coverage_cells(session_id, status);
CREATE INDEX IF NOT EXISTS idx_coverage_cells_latlon ON coverage_cells(lat, lon);
CREATE INDEX IF NOT EXISTS idx_place_categories_category ON place_categories(category);
CREATE INDEX IF NOT EXISTS idx_places_rating_filter ON places(rating) WHERE rating IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_places_fetched ON places(fetched_at) WHERE fetched_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS macro_sectors (
    id_macro INTEGER PRIMARY KEY,
    nombre_macro VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS commercial_archetypes (
    id_arquetipo INTEGER PRIMARY KEY,
    nombre_arquetipo VARCHAR(100),
    descripcion_estrategica TEXT
);

CREATE TABLE IF NOT EXISTS spatial_clusters (
    cluster_espacial INTEGER PRIMARY KEY,
    total_negocios INTEGER,
    rating_promedio DECIMAL(5,2),
    trafico_total INTEGER,
    tasa_actividad DECIMAL(5,2),
    sector_1 INTEGER DEFAULT 0,
    sector_2 INTEGER DEFAULT 0,
    sector_3 INTEGER DEFAULT 0,
    sector_4 INTEGER DEFAULT 0,
    sector_5 INTEGER DEFAULT 0,
    sector_6 INTEGER DEFAULT 0,
    sector_7 INTEGER DEFAULT 0,
    id_colonia_principal INTEGER,
    diagnostico TEXT,
    recomendacion TEXT,
    id_arquetipo INTEGER REFERENCES commercial_archetypes(id_arquetipo)
);

CREATE TABLE IF NOT EXISTS investment_recommendations (
    id SERIAL PRIMARY KEY,
    cluster_espacial INTEGER REFERENCES spatial_clusters(cluster_espacial),
    locales_totales INTEGER,
    trafico_peatonal INTEGER,
    diagnostico TEXT,
    recomendacion TEXT
);

CREATE INDEX IF NOT EXISTS idx_spatial_clusters_arquetipo ON spatial_clusters(id_arquetipo);
CREATE INDEX IF NOT EXISTS idx_spatial_clusters_trafico ON spatial_clusters(trafico_total DESC);

CREATE TABLE IF NOT EXISTS colonias_cdmx (
    id_colonia INTEGER PRIMARY KEY,
    nombre_colonia VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY,
    place_id VARCHAR(255) REFERENCES places(place_id),
    name VARCHAR(255),
    review_rating INTEGER,
    review_text TEXT,
    review_text_clean TEXT,
    text_length INTEGER,
    word_count INTEGER,
    has_emoji BOOLEAN,
    emoji_count INTEGER,
    sentiment_label VARCHAR(10),
    sentiment_score DECIMAL(5,4),
    sentiment_numeric INTEGER
);

CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment_label);
