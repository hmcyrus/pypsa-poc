# MapGeoCapture — Chrome Extension

Captures Google Maps satellite tiles as a fully georeferenced **GeoTIFF** with:

- EPSG:4326 (WGS84) CRS embedded via GeoTIFF 1.1 tags
- `ModelPixelScaleTag` + `ModelTiepointTag` affine geotransform  
- Rich provenance JSON in the `ImageDescription` TIFF tag  
- Companion world file (`.tfw`) for GIS tools that prefer PNG+world  
- Metadata JSON with GSD, bounding box, GDAL one-liners, pipeline hints  

**Academic use only. Respect Google Maps ToS.**

---

## Install (Developer Mode)

```
1. Open Chrome → chrome://extensions
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked"
4. Select the `geotiff-capture-extension/` folder
```

---

## Usage

1. Navigate to **Google Maps** → switch to **Satellite** or **Hybrid** view
2. Zoom to your Area of Interest (zoom ≥ 14 recommended for infrastructure)
3. Click the blue **📡 GeoCapture** button (bottom-right corner)
4. Three files download automatically:
   - `geocapture_z{zoom}_lat_lon_timestamp.tif`  ← primary deliverable
   - `geocapture_...tfw`                          ← world file (ESRI format)
   - `geocapture_..._metadata.json`               ← full provenance

---

## Output Quality by Zoom Level

| Zoom | GSD (equator) | Recommended for |
|------|--------------|-----------------|
| 14   | ~9.5 m/px    | Substation detection |
| 15   | ~4.8 m/px    | Substation + large towers |
| 17   | ~1.2 m/px    | Transmission tower detection |
| 19   | ~0.3 m/px    | Tower component inspection |

---

## Downstream Pipeline

```
GeoTIFF
  │
  ├─► GDAL / rasterio      (reproject, chip, normalise)
  │
  ├─► YOLOv8 / SAM 2       (object detection → pixel bboxes)
  │
  └─► rasterio.transform   (pixel → WGS84 coordinates)
        │
        └─► GeoJSON output  (tower/substation centroids + polygons)
```

### Pixel → WGS84 (Python, 3 lines)

```python
import rasterio

with rasterio.open("geocapture_z17_....tif") as src:
    lon, lat = rasterio.transform.xy(src.transform, row=412, col=287)
    print(f"Detected object at: {lat:.6f}°N, {lon:.6f}°E")
```

---

## GDAL Commands (from metadata JSON)

```bash
# Inspect
gdalinfo geocapture_z17_....tif

# Reproject to UTM Zone 45N (Bangladesh)
gdalwarp -s_srs EPSG:4326 -t_srs EPSG:32645 -r lanczos \
  geocapture_z17_....tif geocapture_UTM45N.tif

# Compress (LZW, tiled COG)
gdal_translate -co COMPRESS=DEFLATE -co PREDICTOR=2 \
  -co TILED=YES -co BLOCKXSIZE=512 -co BLOCKYSIZE=512 \
  geocapture_z17_....tif geocapture_compressed.tif

# Export PNG + verify world file registration
gdal_translate -of PNG geocapture_z17_....tif preview.png
```

---

## File Architecture

```
geotiff-capture-extension/
  manifest.json       MV3 manifest
  background.js       Service worker — tile fetching (no CORS restrictions)
  tile-math.js        Web Mercator math, URL parsing, GSD computation
  geotiff-writer.js   Pure-JS GeoTIFF binary writer (TIFF 6.0 + GeoTIFF 1.1)
  content.js          UI injection, pipeline orchestration
  icons/              Extension icons
```

---

## GeoTIFF Tags Written

| Tag ID | Name | Value |
|--------|------|-------|
| 256 | ImageWidth | px |
| 257 | ImageLength | px |
| 258 | BitsPerSample | [8, 8, 8] |
| 259 | Compression | 1 (uncompressed) |
| 262 | PhotometricInterpretation | 2 (RGB) |
| 270 | ImageDescription | JSON metadata blob |
| 33550 | ModelPixelScaleTag | [dx°, dy°, 0] |
| 33922 | ModelTiepointTag | [0,0,0, west°, north°, 0] |
| 34735 | GeoKeyDirectoryTag | EPSG:4326 keys |

---

## Limitations & Next Steps

- **Compression**: output is uncompressed — run `gdal_translate` with `COMPRESS=DEFLATE` for production
- **Mercator distortion**: pixel scale varies with latitude; use `rasterio.transform.xy()` for sub-pixel accuracy, not the affine approximation
- **Zoom cap**: extension caps at 200 tiles per capture to avoid memory pressure; tile at z≤17 for wide AOIs
- **Satellite version**: tile URL version string is sniffed from the DOM; if Maps changes its URL scheme, update `sniffTileMetaFromDOM()` in `tile-math.js`
