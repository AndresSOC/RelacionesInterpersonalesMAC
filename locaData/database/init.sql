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
    cell_id INT REFERENCES coverage_cells(id)
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
