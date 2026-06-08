/**
 * tile-math.js
 *
 * Web Mercator (EPSG:3857) tile math for Google Maps slippy-map tiles.
 *
 * All Google Maps tiles are 256×256 px using the standard XYZ scheme:
 *   - X increases east
 *   - Y increases south (origin = upper-left = NW)
 *   - Zoom 0 = entire world in one tile; each level doubles resolution
 *
 * Geographic coordinates are WGS84 (EPSG:4326), decimal degrees.
 */

const TileMath = (() => {

  const TILE_PX = 256;        // pixels per tile edge
  const EARTH_R = 6378137;    // WGS84 semi-major axis (metres)
  const MAX_LAT  = 85.0511;   // Mercator north/south limit

  // ── Coordinate Conversions ──────────────────────────────────────────────────

  /** Longitude (degrees) → fractional tile X at zoom Z */
  function lonToTileX(lon, zoom) {
    return (lon + 180) / 360 * Math.pow(2, zoom);
  }

  /** Latitude (degrees, WGS84) → fractional tile Y at zoom Z */
  function latToTileY(lat, zoom) {
    const latRad = clamp(lat, -MAX_LAT, MAX_LAT) * Math.PI / 180;
    const sinLat = Math.sin(latRad);
    return (1 - Math.log((1 + sinLat) / (1 - sinLat)) / (2 * Math.PI)) / 2 * Math.pow(2, zoom);
  }

  /** Fractional tile X → longitude (degrees) */
  function tileXToLon(x, zoom) {
    return x / Math.pow(2, zoom) * 360 - 180;
  }

  /** Fractional tile Y → latitude (degrees, WGS84) */
  function tileYToLat(y, zoom) {
    const n = Math.PI * (1 - 2 * y / Math.pow(2, zoom));
    return 180 / Math.PI * Math.atan(Math.sinh(n));
  }

  // ── Viewport → Tile Grid ────────────────────────────────────────────────────

  /**
   * Given the current map state, compute the integer tile range that
   * covers the viewport plus a configurable buffer (in tiles).
   *
   * Returns:
   *  colMin, colMax, rowMin, rowMax  — inclusive tile indices
   *  globalPixLeft, globalPixTop    — viewport upper-left in global pixel space
   *  stitchOffsetX, stitchOffsetY   — pixel offset from tile grid corner to viewport UL
   *  stitchWidth, stitchHeight      — total canvas size for tile grid (before crop)
   */
  function getViewportTileRange(centerLat, centerLon, zoom, viewW, viewH, buffer = 1) {
    const n = Math.pow(2, zoom);

    // Center in fractional tile coords
    const cx = lonToTileX(centerLon, zoom);
    const cy = latToTileY(centerLat, zoom);

    // Center in global pixel space (origin = NW corner of the world)
    const globalCenterX = cx * TILE_PX;
    const globalCenterY = cy * TILE_PX;

    // Viewport upper-left in global pixel space
    const vpLeft = globalCenterX - viewW / 2;
    const vpTop  = globalCenterY - viewH / 2;

    // Tile indices that cover the viewport (floor = the tile containing that pixel)
    const colMin = Math.max(0,     Math.floor(vpLeft / TILE_PX) - buffer);
    const colMax = Math.min(n - 1, Math.floor((vpLeft + viewW) / TILE_PX) + buffer);
    const rowMin = Math.max(0,     Math.floor(vpTop  / TILE_PX) - buffer);
    const rowMax = Math.min(n - 1, Math.floor((vpTop + viewH)  / TILE_PX) + buffer);

    // The tile grid's upper-left in global pixel space
    const gridLeft = colMin * TILE_PX;
    const gridTop  = rowMin * TILE_PX;

    // Stitched canvas size
    const stitchWidth  = (colMax - colMin + 1) * TILE_PX;
    const stitchHeight = (rowMax - rowMin + 1) * TILE_PX;

    // Pixel offset of viewport UL within the stitched canvas
    const stitchOffsetX = Math.round(vpLeft - gridLeft);
    const stitchOffsetY = Math.round(vpTop  - gridTop);

    return {
      colMin, colMax, rowMin, rowMax,
      globalPixLeft: vpLeft, globalPixTop: vpTop,
      stitchOffsetX, stitchOffsetY,
      stitchWidth, stitchHeight,
      totalTiles: (colMax - colMin + 1) * (rowMax - rowMin + 1)
    };
  }

  // ── Bounding Box ─────────────────────────────────────────────────────────────

  /**
   * Compute the EXACT WGS84 bounding box of a tile grid.
   * Tile boundaries are exact in the Mercator projection,
   * so this gives pixel-perfect georeferencing.
   */
  function getTileBBox(colMin, colMax, rowMin, rowMax, zoom) {
    return {
      west:  tileXToLon(colMin,     zoom),
      east:  tileXToLon(colMax + 1, zoom),
      north: tileYToLat(rowMin,     zoom),
      south: tileYToLat(rowMax + 1, zoom),
    };
  }

  // ── Ground Sample Distance ───────────────────────────────────────────────────

  /**
   * Ground Sample Distance (GSD) in metres per pixel at a given
   * zoom level and latitude.  This is the key quality metric:
   *   - zoom 17 ≈ 1.2 m/px at equator
   *   - zoom 19 ≈ 0.3 m/px at equator
   * GSD shrinks near the poles due to Mercator distortion.
   */
  function getGSD(lat, zoom) {
    return (2 * Math.PI * EARTH_R * Math.cos(lat * Math.PI / 180))
           / (TILE_PX * Math.pow(2, zoom));
  }

  /**
   * Get GSD for a full bounding box — returns min/max/center values
   * since GSD varies with latitude in Mercator.
   */
  function getGSDRange(bbox, zoom) {
    const latCenter = (bbox.north + bbox.south) / 2;
    return {
      atNorthEdge:  getGSD(bbox.north, zoom),
      atCenter:     getGSD(latCenter,  zoom),
      atSouthEdge:  getGSD(bbox.south, zoom),
      minMetersPerPx: getGSD(Math.max(Math.abs(bbox.north), Math.abs(bbox.south)), zoom),
      maxMetersPerPx: getGSD(Math.min(Math.abs(bbox.north), Math.abs(bbox.south)), zoom),
    };
  }

  // ── Pixel ↔ Coordinate ────────────────────────────────────────────────────────

  /**
   * Convert a pixel position (px, py) within the stitched image to WGS84.
   * This is what you use AFTER detection to geo-locate detected objects.
   *
   *   lon = west + px * (east - west) / imageWidth
   *   lat = tileYToLat(rowMin + py / TILE_PX, zoom)  ← NOT linear in lat!
   *
   * Note: longitude IS linear (Mercator is conformal in X).
   * Latitude is NOT linear — use this function for precision.
   */
  function pixelToLatLon(px, py, bbox, imageWidth, imageHeight, rowMin, zoom) {
    const lon = bbox.west + (px / imageWidth) * (bbox.east - bbox.west);
    // Fractional tile Y for this pixel
    const tileY_frac = rowMin + py / TILE_PX;
    const lat = tileYToLat(tileY_frac, zoom);
    return { lat, lon };
  }

  /**
   * Convert WGS84 to pixel within the stitched image.
   * Inverse of pixelToLatLon.
   */
  function latLonToPixel(lat, lon, bbox, imageWidth, imageHeight, rowMin, zoom) {
    const px = (lon - bbox.west) / (bbox.east - bbox.west) * imageWidth;
    const tileY_frac = latToTileY(lat, zoom);
    const py = (tileY_frac - rowMin) * TILE_PX;
    return { px: Math.round(px), py: Math.round(py) };
  }

  // ── Tile URL Construction ────────────────────────────────────────────────────

  /**
   * Parse map state from the Google Maps URL.
   * Google Maps encodes state as: .../@{lat},{lon},{zoom}z...
   * Also handles zoom with 'm' suffix (map) and different URL formats.
   */
  function parseGoogleMapsURL(url) {
    // Primary format: /@lat,lon,zoomz
    const atMatch = url.match(\/@(-?\d+\.\d+),(-?\d+\.\d+),(\d+(?:\.\d+)?)([mza])/);
    if (atMatch) {
      const lat  = parseFloat(atMatch[1]);
      const lon  = parseFloat(atMatch[2]);
      const zoom = Math.round(parseFloat(atMatch[3]));
      return { lat, lon, zoom, confidence: 'high' };
    }
    // Fallback: look for ll= param (older URLs)
    const llMatch = url.match(/[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)/);
    const zMatch  = url.match(/[?&]z=(\d+)/);
    if (llMatch && zMatch) {
      return {
        lat: parseFloat(llMatch[1]),
        lon: parseFloat(llMatch[2]),
        zoom: parseInt(zMatch[1]),
        confidence: 'medium'
      };
    }
    return null;
  }

  /**
   * Sniff tile URL version string and map type from an <img> element
   * currently loaded by Google Maps.
   */
  function sniffTileMetaFromDOM() {
    // Satellite tiles (khm servers)
    const satImg = document.querySelector(
      'img[src*="khm.googleapis.com"], img[src*="khm0.googleapis.com"], ' +
      'img[src*="khm1.googleapis.com"], img[src*="khm2.googleapis.com"], ' +
      'img[src*="khm3.googleapis.com"]'
    );
    if (satImg) {
      const u = new URL(satImg.src);
      return {
        mapType: 'satellite',
        version:  u.searchParams.get('v') || '',
        baseUrl:  `${u.protocol}//${u.host}/kh`
      };
    }
    // Road/hybrid tiles (mt servers)
    const roadImg = document.querySelector(
      'img[src*="mt.googleapis.com"], img[src*="mt0.googleapis.com"], ' +
      'img[src*="mt1.googleapis.com"], img[src*="mt2.googleapis.com"]'
    );
    if (roadImg) {
      const u = new URL(roadImg.src);
      const lyrs = u.searchParams.get('lyrs') || 's'; // s=satellite, h=hybrid, m=road
      return {
        mapType: lyrs === 'm' ? 'roadmap' : lyrs === 'h' ? 'hybrid' : 'satellite',
        version: u.searchParams.get('v') || '',
        lyrs,
        baseUrl: `${u.protocol}//${u.host}/vt`
      };
    }
    return null;
  }

  /**
   * Build a tile fetch URL from tile coordinates and sniffed metadata.
   * Rotates across sub-domains (khm0–3, mt0–3) for parallelism —
   * browsers allow 6 parallel connections per host.
   */
  function buildTileURL(x, y, zoom, tileMeta, tileIndex = 0) {
    if (!tileMeta) return null;
    const subdomain = tileIndex % 4; // 0–3

    if (tileMeta.mapType === 'satellite' || !tileMeta.lyrs) {
      return `https://khm${subdomain}.googleapis.com/kh?v=${tileMeta.version}&x=${x}&y=${y}&z=${zoom}`;
    }
    return `https://mt${subdomain}.googleapis.com/vt?lyrs=${tileMeta.lyrs}&x=${x}&y=${y}&z=${zoom}`;
  }

  // ── Utility ──────────────────────────────────────────────────────────────────

  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

  return {
    TILE_PX,
    lonToTileX, latToTileY, tileXToLon, tileYToLat,
    getViewportTileRange, getTileBBox,
    getGSD, getGSDRange,
    pixelToLatLon, latLonToPixel,
    parseGoogleMapsURL, sniffTileMetaFromDOM, buildTileURL,
  };

})();
