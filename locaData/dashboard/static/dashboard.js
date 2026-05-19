var map;
var heatmapLayer;
var circleLayer = [];
var placeCache = [];
var socket;

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 19.3048, lng: -99.1895 },
        zoom: 14,
        mapTypeControl: true,
        fullscreenControl: true,
        streetViewControl: false,
        zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_BOTTOM }
    });

    loadCoverage();
    loadHeatmap();
    loadSearch();
    loadStatus();
    loadCategories();
    connectSocket();
}

function loadCoverage() {
    fetch('/api/coverage')
        .then(function (r) { return r.json(); })
        .then(function (cells) {
            circleLayer.forEach(function (c) { c.setMap(null); });
            circleLayer = [];
            cells.forEach(function (cell) {
                var circle = new google.maps.Circle({
                    strokeColor: '#1967d2',
                    strokeOpacity: 0.5,
                    strokeWeight: 1,
                    fillColor: '#1967d2',
                    fillOpacity: 0.1,
                    map: map,
                    center: { lat: cell.lat, lng: cell.lon },
                    radius: cell.radius_m
                });
                circleLayer.push(circle);
            });
            var toggle = document.getElementById('toggle-circles');
            if (toggle && !toggle.checked) {
                circleLayer.forEach(function (c) { c.setVisible(false); });
            }
        });
}

function loadHeatmap() {
    fetch('/api/heatmap' + heatmapParams())
        .then(function (r) { return r.json(); })
        .then(function (points) {
            if (heatmapLayer) heatmapLayer.setMap(null);
            var mapped = points.map(function (p) {
                return new google.maps.LatLng(p.lat, p.lng);
            });
            heatmapLayer = new google.maps.visualization.HeatmapLayer({
                data: mapped,
                map: map,
                radius: 25,
                opacity: 0.5
            });
            var toggle = document.getElementById('toggle-heatmap');
            if (toggle && !toggle.checked) {
                heatmapLayer.setMap(null);
            }
        });
}

function heatmapParams() {
    var parts = [];
    var rating = document.getElementById('filter-rating')?.value || '0';
    var reviews = document.getElementById('filter-reviews')?.value || '0';
    var category = document.getElementById('filter-category')?.value || '';
    if (rating > 0) parts.push('min_rating=' + rating);
    if (reviews > 0) parts.push('min_reviews=' + reviews);
    if (category) parts.push('category=' + encodeURIComponent(category));
    return parts.length ? '?' + parts.join('&') : '';
}

function loadCategories() {
    fetch('/api/categories')
        .then(function (r) { return r.json(); })
        .then(function (cats) {
            var sel = document.getElementById('filter-category');
            cats.forEach(function (c) {
                var opt = document.createElement('option');
                opt.value = c;
                opt.textContent = c;
                sel.appendChild(opt);
            });
        });
}

function loadSearch() {
    fetch('/api/search')
        .then(function (r) { return r.json(); })
        .then(function (places) {
            placeCache = places;
            var datalist = document.getElementById('place-list');
            datalist.innerHTML = '';
            var fragment = document.createDocumentFragment();
            places.forEach(function (p) {
                var option = document.createElement('option');
                option.value = p.name;
                option.setAttribute('data-lat', p.lat);
                option.setAttribute('data-lng', p.lng);
                fragment.appendChild(option);
            });
            datalist.appendChild(fragment);
        });
}

function loadStatus() {
    fetch('/api/status')
        .then(function (r) { return r.json(); })
        .then(function (status) {
            var badge = document.getElementById('poll-indicator');
            if (badge) {
                document.getElementById('radius-value').textContent = status.radiusKm || '5';
                if (status.active) {
                    badge.textContent = 'Pipeline ejecutandose... ' + status.totalPlaces + ' lugares';
                } else {
                    badge.textContent = status.totalPlaces + ' lugares cargados';
                }
            }
        });
}

function connectSocket() {
    if (socket) socket.close();
    socket = io();

    socket.on('update', function (data) {
        loadCoverage();
        loadHeatmap();
        var badge = document.getElementById('poll-indicator');
        if (badge) badge.textContent = 'Pipeline ejecutandose... ' + data.totalPlaces + ' lugares';
        var btn = document.getElementById('expand-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Expandiendo...'; }
    });

    socket.on('done', function (data) {
        loadCoverage();
        loadHeatmap();
        loadSearch();
        var badge = document.getElementById('poll-indicator');
        if (badge) badge.textContent = 'Pipeline completado — ' + data.totalPlaces + ' lugares';
        var btn = document.getElementById('expand-btn');
        if (btn) { btn.disabled = false; btn.textContent = 'Expandir'; }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('search');
    input.addEventListener('input', function () {
        var found = placeCache.find(function (p) { return p.name === this.value; }.bind(input));
        if (found) {
            map.setCenter({ lat: found.lat, lng: found.lng });
            map.setZoom(17);
        }
    });

    document.getElementById('toggle-circles').addEventListener('change', function () {
        circleLayer.forEach(function (c) { c.setVisible(this.checked); }.bind(this));
    });

    document.getElementById('toggle-heatmap').addEventListener('change', function () {
        if (heatmapLayer) {
            heatmapLayer.setMap(this.checked ? map : null);
        }
    });

    var slider = document.getElementById('radius-slider');
    slider.addEventListener('input', function () {
        document.getElementById('radius-value').textContent = this.value;
    });

    document.getElementById('expand-btn').addEventListener('click', function () {
        var radius = parseFloat(document.getElementById('radius-slider').value);
        var btn = this;
        btn.disabled = true;
        btn.textContent = 'Expandiendo...';

        fetch('/api/expand', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ radius_km: radius })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.error);
                btn.disabled = false;
                btn.textContent = 'Expandir';
            } else {
                connectSocket();
            }
        });
    });

    document.getElementById('filter-rating').addEventListener('input', function () {
        document.getElementById('rating-label').textContent = this.value;
        loadHeatmap();
    });

    document.getElementById('filter-reviews').addEventListener('change', loadHeatmap);

    document.getElementById('filter-category').addEventListener('change', loadHeatmap);
});
