/**
 * content.js — MapGeoCapture
 *
 * Injected into google.com/maps/* pages.
 * Responsibilities:
 *   1. Parse map state (centre, zoom) from the live URL
 *   2. Sniff tile metadata from the DOM (URL version string, map type)
 *   3. Compute the viewport + buffer tile grid
 *   4. Fetch all tiles via the background SW (no CORS issues)
 *   5. Stitch tiles on an offscreen canvas
 *   6. Write a GeoTIFF (via GeoTIFFWriter) + world file + metadata JSON
 *   7. Trigger all three downloads
 */

(function () {
  'use strict';

  // ── Configuration ──────────────────────────────────────────────────────────
  const TILE_BUFFER   = 1;       // extra tile rows/cols beyond viewport
  const MAX_TILES     = 200;     // safety cap (≈ 14×14 grid)
  const UI_ID         = 'mgc-panel';
  const BTN_ID        = 'mgc-capture-btn';

  // ── State ──────────────────────────────────────────────────────────────────
  let capturing = false;

  // ─────────────────────────────────────────────────────────────────────────────
  // UI Injection
  // ─────────────────────────────────────────────────────────────────────────────

  function injectUI() {
    if (document.getElementById(UI_ID)) return;

    const panel = document.createElement('div');
    panel.id = UI_ID;
    panel.innerHTML = `
      <style>
        #mgc-panel {
          position: fixed;
          bottom: 80px;
          right: 12px;
          z-index: 9999;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
          font-family: 'Google Sans', Roboto, sans-serif;
        }
        #mgc-capture-btn {
          background: #1a73e8;
          color: #fff;
          border: none;
          border-radius: 24px;
          padding: 10px 18px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          box-shadow: 0 2px 8px rgba(0,0,0,0.35);
          display: flex;
          align-items: center;
          gap: 7px;
          transition: background 0.15s, transform 0.1s;
          white-space: nowrap;
        }
        #mgc-capture-btn:hover  { background: #1557b0; }
        #mgc-capture-btn:active { transform: scale(0.97); }
        #mgc-capture-btn:disabled {
          background: #5f6368;
          cursor: not-allowed;
          transform: none;
        }
        #mgc-status {
          background: rgba(0,0,0,0.78);
          color: #e8f0fe;
          border-radius: 10px;
          padding: 8px 14px;
          font-size: 12px;
          max-width: 280px;
          line-height: 1.5;
          display: none;
          backdrop-filter: blur(4px);
        }
        #mgc-status.visible { display: block; }
        #mgc-progress {
          height: 3px;
          background: #1a73e8;
          border-radius: 2px;
          margin-top: 5px;
          transition: width 0.2s;
        }
        #mgc-meta {
          background: rgba(255,255,255,0.93);
          color: #202124;
          border-radius: 10px;
          padding: 10px 14px;
          font-size: 11px;
          max-width: 280px;
          line-height: 1.7;
          display: none;
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        #mgc-meta.visible { display: block; }
        #mgc-meta strong { color: #1a73e8; }
        #mgc-zoom-warning {
          background: #fce8e6;
          color: #c5221f;
          border-radius: 8px;
          padding: 7px 12px;
          font-size: 11px;
          display: none;
        }
        #mgc-zoom-warning.visible { display: block; }
      </style>

      <div id="mgc-zoom-warning">⚠️ Zoom in for better GSD</div>

      <div id="mgc-meta"></div>

      <div id="mgc-status">
        <div id="mgc-status-text">Initialising…</div>
        <div style="background:rgba(255,255,255,0.15);border-radius:2px;margin-top:5px;overflow:hidden;">
          <div id="mgc-progress" style="width:0%;height:3px;background:#8ab4f8;border-radius:2px;transition:width 0.2s;"></div>
        </div>
      </div>

      <button id="${BTN_ID}">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
        </svg>
        GeoCapture
      </button>
    `;
    document.body.appendChild(panel);

    document.getElementById(BTN_ID).addEventListener('click', onCapture);

    // Update zoom warning whenever URL changes
    observeMapState();
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Map state monitoring
  // ─────────────────────────────────────────────────────────────────────────────

  function observeMapState() {
    let lastUrl = location.href;

    const check = () => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        updateZoomWarning();
      }
    };

    setInterval(check, 500); // Google Maps is an SPA; MutationObserver on URL works too
    updateZoomWarning();
  }

  function updateZoomWarning() {
    const state   = TileMath.parseGoogleMapsURL(location.href);
    const warning = document.getElementById('mgc-zoom-warning');
    if (!warning) return;
    if (state && state.zoom < 14) {
      const gsd = TileMath.getGSD(state.lat, state.zoom).toFixed(1);
      warning.textContent = `⚠️ Zoom ${state.zoom} → GSD ≈ ${gsd} m/px. Zoom in ≥14 for infrastructure detection.`;
      warning.classList.add('visible');
    } else {
      warning.classList.remove('visible');
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Status helpers
  // ─────────────────────────────────────────────────────────────────────────────

  function setStatus(text, progress = null) {
    const box = document.getElementById('mgc-status');
    const txt = document.getElementById('mgc-status-text');
    const bar = document.getElementById('mgc-progress');
    if (!box) return;
    box.classList.add('visible');
    txt.textContent = text;
    if (progress !== null) bar.style.width = `${progress}%`;
  }

  function hideStatus() {
    const box = document.getElementById('mgc-status');
    if (box) box.classList.remove('visible');
  }

  function showMeta(html) {
    const el = document.getElementById('mgc-meta');
    if (!el) return;
    el.innerHTML = html;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 12000);
  }

  function setButton(enabled, label = 'GeoCapture') {
    const btn = document.getElementById(BTN_ID);
    if (!btn) return;
    btn.disabled = !enabled;
    btn.childNodes[btn.childNodes.length - 1].textContent = ' ' + label;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Main Capture Pipeline
  // ─────────────────────────────────────────────────────────────────────────────

  async function onCapture() {
    if (capturing) return;
    capturing = true;
    setButton(false, 'Capturing…');

    try {
      await runCapture();
    } catch (err) {
      setStatus('❌ ' + err.message);
      console.error('[MapGeoCapture]', err);
    } finally {
      capturing = false;
      setButton(true, 'GeoCapture');
      setTimeout(hideStatus, 4000);
    }
  }

  async function runCapture() {
    // ── Step 1: Parse map state from URL ──────────────────────────────────
    setStatus('📍 Reading map state…', 5);
    const mapState = TileMath.parseGoogleMapsURL(location.href);
    if (!mapState) throw new Error('Could not parse map centre/zoom from URL. Pan or zoom slightly and retry.');

    const { lat, lon, zoom } = mapState;

    // ── Step 2: Sniff tile version from DOM ───────────────────────────────
    setStatus('🔍 Detecting tile metadata…', 10);
    const tileMeta = TileMath.sniffTileMetaFromDOM();
    if (!tileMeta) throw new Error('No map tiles found in DOM. Ensure satellite or hybrid mode is active.');

    // ── Step 3: Compute tile grid ─────────────────────────────────────────
    setStatus('🗺️ Computing tile grid…', 15);
    const mapDiv  = document.getElementById('map') || document.querySelector('[id^="map"]') || document.body;
    const viewW   = window.innerWidth;
    const viewH   = window.innerHeight;

    const grid = TileMath.getViewportTileRange(lat, lon, zoom, viewW, viewH, TILE_BUFFER);
    const bbox = TileMath.getTileBBox(grid.colMin, grid.colMax, grid.rowMin, grid.rowMax, zoom);
    const gsd  = TileMath.getGSDRange(bbox, zoom);

    if (grid.totalTiles > MAX_TILES) {
      throw new Error(`Tile count (${grid.totalTiles}) exceeds safety cap of ${MAX_TILES}. Zoom in or reduce buffer.`);
    }

    console.log('[MapGeoCapture] Grid:', grid);
    console.log('[MapGeoCapture] BBox:', bbox);
    console.log('[MapGeoCapture] GSD (m/px):', gsd);

    // ── Step 4: Build tile URL list ───────────────────────────────────────
    setStatus(`📦 Queuing ${grid.totalTiles} tiles…`, 20);
    const tileList = [];
    let idx = 0;
    for (let row = grid.rowMin; row <= grid.rowMax; row++) {
      for (let col = grid.colMin; col <= grid.colMax; col++) {
        const url = TileMath.buildTileURL(col, row, zoom, tileMeta, idx++);
        tileList.push({ col, row, url });
      }
    }

    // ── Step 5: Fetch tiles via background SW ────────────────────────────
    setStatus(`🌐 Fetching ${tileList.length} tiles…`, 25);
    const urls = tileList.map(t => t.url);

    let fetchedCount = 0;
    const tileDataMap = {}; // url → base64

    // Batch fetch with progress reporting
    const BATCH = 20;
    for (let i = 0; i < urls.length; i += BATCH) {
      const batchUrls = urls.slice(i, i + BATCH);
      const response  = await sendMessage({ type: 'FETCH_TILES_BATCH', urls: batchUrls });
      if (!response?.results) throw new Error('Background SW did not respond. Reload the extension.');
      Object.assign(tileDataMap, response.results);
      fetchedCount += batchUrls.length;
      const pct = 25 + Math.round((fetchedCount / urls.length) * 40);
      setStatus(`🌐 Fetched ${fetchedCount}/${urls.length} tiles…`, pct);
    }

    // ── Step 6: Decode tiles and stitch onto canvas ───────────────────────
    setStatus('🧵 Stitching tiles…', 66);
    const canvas  = new OffscreenCanvas(grid.stitchWidth, grid.stitchHeight);
    const ctx     = canvas.getContext('2d');

    let stitchFailed = 0;
    const tilePromises = tileList.map(({ col, row, url }) =>
      decodeTileImage(tileDataMap[url])
        .then(img => {
          const dx = (col - grid.colMin) * TileMath.TILE_PX;
          const dy = (row - grid.rowMin) * TileMath.TILE_PX;
          ctx.drawImage(img, dx, dy);
        })
        .catch(() => { stitchFailed++; })
    );
    await Promise.all(tilePromises);

    if (stitchFailed > 0) {
      console.warn(`[MapGeoCapture] ${stitchFailed} tiles failed to decode.`);
    }

    // ── Step 7: Extract pixel data ────────────────────────────────────────
    setStatus('🖼️ Extracting pixels…', 75);
    const imageData = ctx.getImageData(0, 0, grid.stitchWidth, grid.stitchHeight);

    // ── Step 8: Build rich metadata JSON ─────────────────────────────────
    setStatus('📋 Encoding metadata…', 80);
    const captureTime = new Date().toISOString();
    const filenameBase = `geocapture_z${zoom}_${lat.toFixed(5)}_${lon.toFixed(5)}_${captureTime.slice(0,19).replace(/[:.]/g,'-')}`;

    const metadata = {
      tool:          'MapGeoCapture v1.0',
      captured_utc:  captureTime,
      crs:           'EPSG:4326 (WGS84 Geographic)',
      source: {
        origin:      'Google Maps satellite tiles',
        map_type:    tileMeta.mapType,
        tile_version:tileMeta.version,
        zoom_level:  zoom,
      },
      image: {
        width_px:    grid.stitchWidth,
        height_px:   grid.stitchHeight,
        tiles_x:     grid.colMax - grid.colMin + 1,
        tiles_y:     grid.rowMax - grid.rowMin + 1,
        tile_buffer: TILE_BUFFER,
        total_tiles: grid.totalTiles,
        tiles_failed:stitchFailed,
      },
      bounding_box: {
        west:  bbox.west,
        south: bbox.south,
        east:  bbox.east,
        north: bbox.north,
        description: 'WGS84 decimal degrees',
      },
      geotransform: {
        pixel_scale_x_deg: (bbox.east  - bbox.west)  / grid.stitchWidth,
        pixel_scale_y_deg: (bbox.north - bbox.south) / grid.stitchHeight,
        upper_left_lon: bbox.west,
        upper_left_lat: bbox.north,
        model: 'ModelPixelScaleTag + ModelTiepointTag (GeoTIFF 1.1)',
      },
      gsd_metres: {
        at_north_edge:  +gsd.atNorthEdge.toFixed(4),
        at_centre:      +gsd.atCenter.toFixed(4),
        at_south_edge:  +gsd.atSouthEdge.toFixed(4),
      },
      map_centre: { lat, lon },
      viewport_px: { width: viewW, height: viewH },
      gdal_commands: {
        info:    `gdalinfo ${filenameBase}.tif`,
        reproject: `gdalwarp -s_srs EPSG:4326 -t_srs EPSG:32645 -r lanczos ${filenameBase}.tif ${filenameBase}_UTM45N.tif`,
        compress: `gdal_translate -co COMPRESS=DEFLATE -co PREDICTOR=2 -co TILED=YES ${filenameBase}.tif ${filenameBase}_compressed.tif`,
        png_world: `gdal_translate -of PNG ${filenameBase}.tif ${filenameBase}.png`,
      },
      pipeline_hint: 'Feed the GeoTIFF into your object-detection model. ' +
        'After detecting bounding boxes (px), call rasterio.transform.xy(transform, row, col) ' +
        'to get WGS84 coordinates for each detected tower/substation.',
    };

    // ── Step 9: Write GeoTIFF ─────────────────────────────────────────────
    setStatus('📐 Writing GeoTIFF…', 87);
    const geoTiffBuffer = GeoTIFFWriter.write(
      imageData.data,           // RGBA Uint8ClampedArray
      grid.stitchWidth,
      grid.stitchHeight,
      {
        west:        bbox.west,
        south:       bbox.south,
        east:        bbox.east,
        north:       bbox.north,
        description: JSON.stringify(metadata),
      }
    );

    // ── Step 10: Build world file ──────────────────────────────────────────
    const worldFile = GeoTIFFWriter.buildWorldFile(
      bbox.west, bbox.north, bbox.east, bbox.south,
      grid.stitchWidth, grid.stitchHeight
    );

    // ── Step 11: Download all three outputs ────────────────────────────────
    setStatus('💾 Downloading outputs…', 95);

    // 1) GeoTIFF — primary deliverable
    GeoTIFFWriter.downloadBuffer(geoTiffBuffer, `${filenameBase}.tif`, 'image/tiff');

    await sleep(300);

    // 2) World file (.tfw) — companion for PNG fallback
    GeoTIFFWriter.downloadBuffer(
      new TextEncoder().encode(worldFile),
      `${filenameBase}.tfw`,
      'text/plain'
    );

    await sleep(300);

    // 3) Metadata JSON — full provenance record
    GeoTIFFWriter.downloadBuffer(
      new TextEncoder().encode(JSON.stringify(metadata, null, 2)),
      `${filenameBase}_metadata.json`,
      'application/json'
    );

    // ── Step 12: Show summary panel ────────────────────────────────────────
    setStatus('✅ Done!', 100);
    showMeta(`
      <strong>📡 GeoCapture complete</strong><br>
      📐 ${grid.stitchWidth} × ${grid.stitchHeight} px<br>
      🔍 GSD: <strong>${gsd.atCenter.toFixed(2)} m/px</strong> at centre<br>
      🗺️ ${grid.totalTiles} tiles (zoom ${zoom})<br>
      📦 ${(geoTiffBuffer.byteLength / 1024 / 1024).toFixed(1)} MB GeoTIFF<br>
      🌍 W:${bbox.west.toFixed(5)} S:${bbox.south.toFixed(5)}<br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;E:${bbox.east.toFixed(5)} N:${bbox.north.toFixed(5)}<br>
      <span style="color:#5f6368;font-size:10px">3 files downloaded ↓</span>
    `);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Helpers
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Decode a base64 tile image string into an ImageBitmap for drawing.
   * Falls back to a grey placeholder if decoding fails.
   */
  function decodeTileImage(result) {
    return new Promise((resolve, reject) => {
      if (!result?.ok || !result.data) return reject(new Error('No tile data'));

      const mime  = result.mime || 'image/jpeg';
      const bytes = Uint8Array.from(atob(result.data), c => c.charCodeAt(0));
      const blob  = new Blob([bytes], { type: mime });

      createImageBitmap(blob)
        .then(resolve)
        .catch(reject);
    });
  }

  /** Promisified chrome.runtime.sendMessage */
  function sendMessage(msg) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(msg, response => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ─────────────────────────────────────────────────────────────────────────────
  // Bootstrap — wait for Maps UI to be ready before injecting button
  // ─────────────────────────────────────────────────────────────────────────────

  function waitForMap(cb, maxWait = 10000) {
    const start = Date.now();
    const check = () => {
      // Google Maps renders a canvas or img tiles in the DOM; wait for them
      const hasMap = document.querySelector('[id^="map"], .widget-scene-canvas, #scene')
                  || document.querySelector('img[src*="googleapis.com"]');
      if (hasMap) {
        cb();
      } else if (Date.now() - start < maxWait) {
        setTimeout(check, 500);
      } else {
        // Inject anyway — user may be on a view without tiles yet
        cb();
      }
    };
    check();
  }

  waitForMap(injectUI);

})();
