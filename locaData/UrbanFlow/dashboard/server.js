const express = require('express');
const { Pool } = require('pg');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const pool = new Pool({
  host: 'localhost',
  port: 5441,
  user: 'postgres',
  password: 'postgres',
  database: 'locadata',
  connectionTimeoutMillis: 2000,
  idleTimeoutMillis: 30000,
  max: 5,
});

const app = express();
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/categories', async (_req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT pc.category, COUNT(*)::INT AS count
      FROM place_categories pc
      GROUP BY pc.category
      ORDER BY count DESC
    `);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/places/geojson', async (req, res) => {
  const { archetype, category, min_rating } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(f ORDER BY ord DESC NULLS LAST), '[]'::json)
      ) AS geojson
      FROM (
        SELECT json_build_object(
          'type', 'Feature',
          'geometry', json_build_object(
            'type', 'Point',
            'coordinates', json_build_array(p.longitud, p.latitud)
          ),
          'properties', json_build_object(
            'place_id', p.place_id,
            'business_name', p.business_name,
            'rating', p.rating,
            'user_ratings_total', p.user_ratings_total,
            'vicinity', p.vicinity,
            'business_status', p.business_status,
            'price_level', p.price_level,
            'cluster_espacial', p.cluster_espacial
          )
        ) AS f,
        p.user_ratings_total AS ord
        FROM places p
        LEFT JOIN spatial_clusters sc ON p.cluster_espacial = sc.cluster_espacial
        WHERE ($1::int IS NULL OR sc.id_arquetipo = $1::int)
        AND ($2::text IS NULL OR EXISTS (
          SELECT 1 FROM place_categories pc WHERE pc.place_id = p.place_id AND pc.category = $2
        ))
        AND ($3::float IS NULL OR p.rating >= $3::float)
        AND p.latitud IS NOT NULL
        AND p.longitud IS NOT NULL
        ORDER BY p.user_ratings_total DESC NULLS LAST
      ) sub
    `, [
      archetype ? parseInt(archetype) : null,
      category || null,
      min_rating ? parseFloat(min_rating) : null
    ]);
    res.json(rows[0]?.geojson || { type: 'FeatureCollection', features: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/summary', async (req, res) => {
  const { archetype, category, min_rating } = req.query;
  try {
    const { rows: stats } = await pool.query(`
      SELECT
        COUNT(*)::INT AS total_places,
        ROUND(AVG(p.rating)::numeric, 2) AS avg_rating,
        (SELECT COUNT(DISTINCT pc2.category) FROM place_categories pc2)::INT AS total_categories
      FROM places p
      LEFT JOIN spatial_clusters sc ON p.cluster_espacial = sc.cluster_espacial
      WHERE ($1::int IS NULL OR sc.id_arquetipo = $1::int)
      AND ($2::text IS NULL OR EXISTS (
        SELECT 1 FROM place_categories pc WHERE pc.place_id = p.place_id AND pc.category = $2
      ))
      AND ($3::float IS NULL OR p.rating >= $3::float)
    `, [
      archetype ? parseInt(archetype) : null,
      category || null,
      min_rating ? parseFloat(min_rating) : null
    ]);

    const { rows: topCats } = await pool.query(`
      SELECT pc.category, COUNT(*)::INT AS count
      FROM place_categories pc
      JOIN places p ON p.place_id = pc.place_id
      LEFT JOIN spatial_clusters sc ON p.cluster_espacial = sc.cluster_espacial
      WHERE ($1::int IS NULL OR sc.id_arquetipo = $1::int)
      AND ($2::text IS NULL OR pc.category = $2)
      AND ($3::float IS NULL OR p.rating >= $3::float)
      GROUP BY pc.category
      ORDER BY count DESC
      LIMIT 10
    `, [
      archetype ? parseInt(archetype) : null,
      category || null,
      min_rating ? parseFloat(min_rating) : null
    ]);

    res.json({ ...stats[0], top_categories: topCats });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/rating-distribution', async (req, res) => {
  const { category, min_rating } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT
        CASE
          WHEN p.rating >= 4.5 THEN '4.5-5.0'
          WHEN p.rating >= 4.0 THEN '4.0-4.5'
          WHEN p.rating >= 3.5 THEN '3.5-4.0'
          WHEN p.rating >= 3.0 THEN '3.0-3.5'
          WHEN p.rating >= 2.0 THEN '2.0-3.0'
          WHEN p.rating >= 1.0 THEN '1.0-2.0'
          ELSE 'Sin rating'
        END AS range,
        COUNT(*)::INT AS count
      FROM places p
      WHERE ($1::text IS NULL OR EXISTS (
        SELECT 1 FROM place_categories pc WHERE pc.place_id = p.place_id AND pc.category = $1
      ))
      AND ($2::float IS NULL OR p.rating >= $2::float)
      GROUP BY range
      ORDER BY MIN(p.rating) DESC NULLS LAST
    `, [category || null, min_rating ? parseFloat(min_rating) : null]);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/sectors', async (_req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT id_macro, nombre_macro FROM macro_sectors ORDER BY id_macro'
    );
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/archetypes', async (_req, res) => {
  try {
    const { rows } = await pool.query(
      'SELECT * FROM commercial_archetypes ORDER BY id_arquetipo'
    );
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/clusters/geojson', async (req, res) => {
  const { archetype } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(
          json_build_object(
            'type', 'Feature',
            'geometry', json_build_object(
              'type', 'Point',
              'coordinates', json_build_array(centroid.lon, centroid.lat)
            ),
            'properties', json_build_object(
              'cluster_espacial', sc.cluster_espacial,
              'total_negocios', sc.total_negocios,
              'rating_promedio', sc.rating_promedio,
              'trafico_total', sc.trafico_total,
              'tasa_actividad', sc.tasa_actividad,
              'nombre_arquetipo', ca.nombre_arquetipo,
              'nombre_colonia', col.nombre_colonia,
              'id_arquetipo', sc.id_arquetipo
            )
          ) ORDER BY sc.trafico_total DESC
        ), '[]'::json)
      ) AS geojson
      FROM spatial_clusters sc
      LEFT JOIN commercial_archetypes ca ON sc.id_arquetipo = ca.id_arquetipo
      LEFT JOIN colonias_cdmx col ON sc.id_colonia_principal = col.id_colonia
      CROSS JOIN LATERAL (
        SELECT AVG(p.latitud) AS lat, AVG(p.longitud) AS lon
        FROM places p
        WHERE p.cluster_espacial = sc.cluster_espacial
          AND p.latitud IS NOT NULL AND p.longitud IS NOT NULL
      ) centroid
      WHERE ($1::int IS NULL OR sc.id_arquetipo = $1)
        AND centroid.lat IS NOT NULL
    `, [archetype ? parseInt(archetype) : null]);
    res.json(rows[0]?.geojson || { type: 'FeatureCollection', features: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/clusters/profiles', async (req, res) => {
  const { archetype } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT sc.*, ca.nombre_arquetipo, col.nombre_colonia
      FROM spatial_clusters sc
      LEFT JOIN commercial_archetypes ca ON sc.id_arquetipo = ca.id_arquetipo
      LEFT JOIN colonias_cdmx col ON sc.id_colonia_principal = col.id_colonia
      WHERE ($1::int IS NULL OR sc.id_arquetipo = $1)
      ORDER BY sc.trafico_total DESC
    `, [archetype ? parseInt(archetype) : null]);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/clusters/:id/detail', async (req, res) => {
  const { id } = req.params;
  try {
    const { rows } = await pool.query(`
      SELECT sc.*, ca.nombre_arquetipo, ca.descripcion_estrategica,
             ir.locales_totales as ir_locales, ir.trafico_peatonal as ir_trafico,
             ir.diagnostico as ir_diagnostico, ir.recomendacion as ir_recomendacion,
             col.nombre_colonia
      FROM spatial_clusters sc
      LEFT JOIN commercial_archetypes ca ON sc.id_arquetipo = ca.id_arquetipo
      LEFT JOIN investment_recommendations ir ON sc.cluster_espacial = ir.cluster_espacial
      LEFT JOIN colonias_cdmx col ON sc.id_colonia_principal = col.id_colonia
      WHERE sc.cluster_espacial = $1
    `, [id]);
    if (!rows[0]) return res.status(404).json({ error: 'Cluster no encontrado' });
    res.json(rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/recommendations', async (_req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT ir.*, sc.total_negocios, sc.rating_promedio, sc.tasa_actividad,
             ca.nombre_arquetipo
      FROM investment_recommendations ir
      JOIN spatial_clusters sc ON ir.cluster_espacial = sc.cluster_espacial
      LEFT JOIN commercial_archetypes ca ON sc.id_arquetipo = ca.id_arquetipo
      ORDER BY ir.trafico_peatonal DESC
    `);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/places/:id/reviews', async (req, res) => {
  const { id } = req.params;
  try {
    const { rows } = await pool.query(`
      SELECT review_id, review_rating, review_text_clean, review_text,
             sentiment_label, sentiment_score, text_length, word_count
      FROM reviews
      WHERE place_id = $1
      ORDER BY sentiment_score DESC NULLS LAST
      LIMIT 20
    `, [id]);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/reviews/sentiment', async (req, res) => {
  const { archetype } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT r.sentiment_label, COUNT(*)::INT AS count
      FROM reviews r
      ${archetype ? `
      JOIN places p ON r.place_id = p.place_id
      JOIN spatial_clusters sc ON p.cluster_espacial = sc.cluster_espacial
      ` : ''}
      ${archetype ? 'WHERE sc.id_arquetipo = $1' : ''}
      GROUP BY r.sentiment_label
      ORDER BY COUNT(*) DESC
    `, archetype ? [parseInt(archetype)] : []);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/reviews/top', async (req, res) => {
  const { sentiment, limit = 15 } = req.query;
  try {
    const { rows } = await pool.query(`
      SELECT r.review_id, r.place_id, r.name, r.review_rating, r.review_text_clean,
             r.sentiment_label, r.sentiment_score, r.word_count
      FROM reviews r
      WHERE ($1::text IS NULL OR r.sentiment_label = $1)
      ORDER BY r.sentiment_score DESC NULLS LAST
      LIMIT $2
    `, [sentiment || null, parseInt(limit)]);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const proxyPredict = (targetPath) => (req, res) => {
  const bodyData = JSON.stringify(req.body || {});
  const opts = {
    hostname: '127.0.0.1',
    port: 5001,
    path: targetPath,
    method: req.method,
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(bodyData) },
  };
  const proxyReq = http.request(opts, (proxyRes) => {
    let data = '';
    proxyRes.on('data', chunk => data += chunk);
    proxyRes.on('end', () => {
      res.status(proxyRes.statusCode);
      try { res.json(JSON.parse(data)); } catch(e) { res.send(data); }
    });
  });
  proxyReq.on('error', (err) => { console.error('Proxy error:', err.message); res.status(503).json({ error: 'Prediction service unavailable' }); });
  if (req.method === 'POST') proxyReq.write(bodyData);
  proxyReq.end();
};

app.get('/api/predict/health', proxyPredict('/api/health'));
app.get('/api/predict/model-info', proxyPredict('/api/model-info'));
app.get('/api/predict/categories', proxyPredict('/api/categories'));
app.post('/api/predict/predict', (req, res) => {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    try { req.body = JSON.parse(body); } catch(e) { req.body = {}; }
    proxyPredict('/api/predict')(req, res);
  });
});

const servidor = app.listen(0, () => {
  console.log('locadata Dashboard API en http://localhost:' + servidor.address().port);
  const flaskPy = path.join(__dirname, 'predict_server.py');
  const venvPython = path.join(__dirname, '..', '..', '..', '.venv', 'bin', 'python3');
  const pythonBin = require('fs').existsSync(venvPython) ? venvPython : 'python3';
  console.log('Iniciando servicio de predicción en :5001...');
  const flask = spawn(pythonBin, [flaskPy, '5001'], {
    cwd: path.join(__dirname, '..', '..'),
    stdio: 'ignore',
    detached: true,
  });
  flask.unref();
});
