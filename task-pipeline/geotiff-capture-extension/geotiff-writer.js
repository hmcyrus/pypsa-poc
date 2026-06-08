/**
 * geotiff-writer.js
 *
 * Writes a valid, spec-compliant GeoTIFF (TIFF 6.0 + GeoTIFF 1.1) entirely
 * in the browser — no native libraries, no server round-trip.
 *
 * Output characteristics:
 *   - Little-endian TIFF (II)
 *   - RGB, 8-bit per channel (3 samples/pixel)
 *   - Uncompressed (Compression = 1) — GDAL can recompress afterward
 *   - CRS: EPSG:4326 (WGS84 Geographic, degrees)
 *   - Affine geotransform via ModelPixelScaleTag + ModelTiepointTag
 *   - Full GeoKeyDirectory (GTModelTypeGeoKey, GTRasterTypeGeoKey,
 *     GeographicTypeGeoKey, GeogAngularUnitsGeoKey)
 *   - Rich metadata in TIFF ImageDescription tag (JSON)
 *
 * Usage:
 *   const buffer = GeoTIFFWriter.write(rgbaUint8, width, height, geoParams);
 *   // geoParams: { west, south, east, north, description (string) }
 */

const GeoTIFFWriter = (() => {

  // ── TIFF Tag IDs ─────────────────────────────────────────────────────────────
  const TAG = {
    ImageWidth:                  256,
    ImageLength:                 257,
    BitsPerSample:               258,
    Compression:                 259,
    PhotometricInterpretation:   262,
    ImageDescription:            270,
    StripOffsets:                273,
    SamplesPerPixel:             277,
    RowsPerStrip:                278,
    StripByteCounts:             279,
    PlanarConfiguration:         284,
    ModelPixelScaleTag:        33550,
    ModelTiepointTag:          33922,
    GeoKeyDirectoryTag:        34735,
    GeoAsciiParamsTag:         34737,
  };

  // ── TIFF Type codes ───────────────────────────────────────────────────────────
  const TYPE = { BYTE: 1, ASCII: 2, SHORT: 3, LONG: 4, DOUBLE: 12 };
  const TYPE_BYTES = { 1: 1, 2: 1, 3: 2, 4: 4, 12: 8 };

  // ── GeoTIFF Key IDs ───────────────────────────────────────────────────────────
  // GTModelTypeGeoKey values
  const ModelTypeGeographic  = 2;
  // GTRasterTypeGeoKey values
  const RasterPixelIsArea    = 1;
  // GeographicTypeGeoKey
  const GCS_WGS_84           = 4326;
  // GeogAngularUnitsGeoKey
  const Angular_Degree        = 9102;

  // ─────────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * @param {Uint8ClampedArray|Uint8Array} pixelData
   *   RGBA or RGB pixel data in row-major order (top → bottom).
   * @param {number} width   Image width in pixels.
   * @param {number} height  Image height in pixels.
   * @param {object} geo
   *   { west, south, east, north }  — WGS84 bounding box of the image.
   *   { description }               — JSON string to embed in ImageDescription.
   * @returns {ArrayBuffer} GeoTIFF file contents.
   */
  function write(pixelData, width, height, geo) {
    // ── 1. Convert RGBA → RGB (TIFF stores RGB only) ────────────────────────
    const isRGBA = pixelData.length === width * height * 4;
    const rgb = isRGBA ? rgbaToRgb(pixelData, width, height) : pixelData;

    // ── 2. Compute pixel scale (degrees per pixel) ────────────────────────
    const pixelScaleX = (geo.east  - geo.west)  / width;   // degrees/px east
    const pixelScaleY = (geo.north - geo.south)  / height;  // degrees/px south

    // ModelPixelScaleTag: [ScaleX, ScaleY, ScaleZ]
    //   ScaleY is positive here; the standard specifies the MAGNITUDE.
    //   The tiepoint anchors upper-left → north, so the sign is implicit.
    const pixelScale  = [pixelScaleX, pixelScaleY, 0.0];

    // ModelTiepointTag: [I, J, K, X, Y, Z]
    //   Maps pixel (0,0) to geographic (west, north, 0).
    const tiepoint    = [0.0, 0.0, 0.0, geo.west, geo.north, 0.0];

    // ── 3. GeoKeyDirectory (EPSG:4326) ───────────────────────────────────
    // Structure: [KeyDirVersion, KeyRevision, MinorRevision, NumKeys,
    //             KeyID, TIFFTagLoc, Count, Value, ...]
    // TIFFTagLoc = 0 means value is in the SHORT Value field directly.
    const geoKeys = new Uint16Array([
      1, 1, 0, 4,                       // Header: v1.1.0, 4 keys
      1024, 0, 1, ModelTypeGeographic,  // GTModelTypeGeoKey
      1025, 0, 1, RasterPixelIsArea,    // GTRasterTypeGeoKey
      2048, 0, 1, GCS_WGS_84,           // GeographicTypeGeoKey → EPSG:4326
      2054, 0, 1, Angular_Degree,       // GeogAngularUnitsGeoKey → degrees
    ]);

    // ── 4. Image description (rich metadata JSON) ─────────────────────────
    const descStr   = (geo.description || '') + '\0'; // null-terminated ASCII
    const descBytes = new TextEncoder().encode(descStr);

    // ── 5. Strip layout ─────────────────────────────────────────────────
    // One strip = one row. This maximises compatibility with streaming readers.
    // StripByteCounts[row] = width * 3 (always the same for uncompressed RGB)
    const bytesPerRow    = width * 3;
    const stripCount     = height;
    const stripByteCount = bytesPerRow; // constant across all strips

    // ── 6. Allocate the output buffer and write everything ──────────────
    return buildBuffer({
      rgb, width, height,
      pixelScale, tiepoint, geoKeys,
      descBytes,
      stripCount, bytesPerRow, stripByteCount
    });
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Internal — binary layout construction
  // ─────────────────────────────────────────────────────────────────────────────

  function buildBuffer(p) {
    const { rgb, width, height, pixelScale, tiepoint,
            geoKeys, descBytes, stripCount, bytesPerRow, stripByteCount } = p;

    // ── Calculate sizes of variable-length data blocks ──────────────────
    const bitsPerSampleData   = 3 * TYPE_BYTES[TYPE.SHORT];     // [8,8,8]
    const stripOffsetsSize    = stripCount * TYPE_BYTES[TYPE.LONG];
    const stripByteCountsSize = stripCount * TYPE_BYTES[TYPE.LONG];
    const pixelScaleSize      = 3 * TYPE_BYTES[TYPE.DOUBLE];
    const tiepointSize        = 6 * TYPE_BYTES[TYPE.DOUBLE];
    const geoKeysSize         = geoKeys.length * TYPE_BYTES[TYPE.SHORT];
    const descSize            = descBytes.length;
    const imageDataSize       = rgb.length;  // width * height * 3

    // ── Compute absolute offsets ────────────────────────────────────────
    // Layout:
    //   [0]     TIFF Header        8 bytes
    //   [8]     IFD                2 + N*12 + 4 bytes
    //   [ifd+]  Extra data area    (values that don't fit in 4-byte IFD value)
    //   [...]   Image strip data   (raw RGB rows)

    const NUM_ENTRIES = 14;
    const ifdOffset   = 8;
    const ifdSize     = 2 + NUM_ENTRIES * 12 + 4;

    // Extra data area starts right after IFD
    let extraOffset = ifdOffset + ifdSize;

    // Assign offsets for each extra block (in the order we'll write them)
    const off_bitsPerSample   = extraOffset; extraOffset += bitsPerSampleData;
    const off_desc            = extraOffset; extraOffset += descSize;
    const off_pixelScale      = extraOffset; extraOffset += pixelScaleSize;
    const off_tiepoint        = extraOffset; extraOffset += tiepointSize;
    const off_geoKeys         = extraOffset; extraOffset += geoKeysSize;
    const off_stripOffsets    = extraOffset; extraOffset += stripOffsetsSize;
    const off_stripByteCounts = extraOffset; extraOffset += stripByteCountsSize;

    // Image data starts after all extra data
    const imageDataOffset = extraOffset;

    const totalSize = imageDataOffset + imageDataSize;
    const buffer    = new ArrayBuffer(totalSize);
    const view      = new DataView(buffer);
    const bytes     = new Uint8Array(buffer);

    let pos = 0; // write cursor

    // ── Helper writers ───────────────────────────────────────────────────
    const wU8  = (v)          => { view.setUint8(pos, v);              pos += 1; };
    const wU16 = (v)          => { view.setUint16(pos, v, true);       pos += 2; };
    const wU32 = (v)          => { view.setUint32(pos, v, true);       pos += 4; };
    const wF64 = (v)          => { view.setFloat64(pos, v, true);      pos += 8; };
    const wAt  = (at, fn, v)  => { const save = pos; pos = at; fn(v); pos = save; };

    function writeIFDEntry(tag, type, count, valueOrOffset) {
      wU16(tag);
      wU16(type);
      wU32(count);
      const byteWidth = TYPE_BYTES[type] * count;
      if (byteWidth <= 4) {
        // Value fits inline — write value, then pad to 4 bytes
        if (type === TYPE.SHORT) {
          if (count === 1) { wU16(valueOrOffset); wU16(0); }
          else { /* inline shorts — shouldn't happen for count > 2 */ wU32(valueOrOffset); }
        } else if (type === TYPE.LONG) {
          wU32(valueOrOffset);
        } else {
          wU32(valueOrOffset);
        }
      } else {
        // Value is an offset into the extra data area
        wU32(valueOrOffset);
      }
    }

    // ── TIFF Header ──────────────────────────────────────────────────────
    // 'II' = little-endian byte order
    wU8(0x49); wU8(0x49);
    wU16(42);           // TIFF magic number
    wU32(ifdOffset);    // Offset to first IFD

    // ── IFD ─────────────────────────────────────────────────────────────
    wU16(NUM_ENTRIES);  // Number of directory entries

    // Tags MUST be in ascending order
    writeIFDEntry(TAG.ImageWidth,               TYPE.LONG,   1, width);
    writeIFDEntry(TAG.ImageLength,              TYPE.LONG,   1, height);
    writeIFDEntry(TAG.BitsPerSample,            TYPE.SHORT,  3, off_bitsPerSample);
    writeIFDEntry(TAG.Compression,              TYPE.SHORT,  1, 1);     // No compression
    writeIFDEntry(TAG.PhotometricInterpretation,TYPE.SHORT,  1, 2);     // RGB
    writeIFDEntry(TAG.ImageDescription,         TYPE.ASCII,  descSize,  off_desc);
    writeIFDEntry(TAG.StripOffsets,             TYPE.LONG,   stripCount, off_stripOffsets);
    writeIFDEntry(TAG.SamplesPerPixel,          TYPE.SHORT,  1, 3);
    writeIFDEntry(TAG.RowsPerStrip,             TYPE.LONG,   1, 1);     // 1 row per strip
    writeIFDEntry(TAG.StripByteCounts,          TYPE.LONG,   stripCount, off_stripByteCounts);
    writeIFDEntry(TAG.PlanarConfiguration,      TYPE.SHORT,  1, 1);     // Chunky (RGBRGB...)
    writeIFDEntry(TAG.ModelPixelScaleTag,       TYPE.DOUBLE, 3, off_pixelScale);
    writeIFDEntry(TAG.ModelTiepointTag,         TYPE.DOUBLE, 6, off_tiepoint);
    writeIFDEntry(TAG.GeoKeyDirectoryTag,       TYPE.SHORT,  geoKeys.length, off_geoKeys);

    wU32(0); // Next IFD offset = 0 (this is the last IFD)

    // ── Extra data area ───────────────────────────────────────────────────

    // BitsPerSample: [8, 8, 8]
    pos = off_bitsPerSample;
    wU16(8); wU16(8); wU16(8);

    // ImageDescription: UTF-8 JSON blob
    pos = off_desc;
    bytes.set(descBytes, pos); pos += descBytes.length;

    // ModelPixelScaleTag: [scaleX, scaleY, 0.0]
    pos = off_pixelScale;
    for (const v of pixelScale) wF64(v);

    // ModelTiepointTag: [I, J, K, X, Y, Z]
    pos = off_tiepoint;
    for (const v of tiepoint) wF64(v);

    // GeoKeyDirectoryTag
    pos = off_geoKeys;
    for (const v of geoKeys) wU16(v);

    // StripOffsets: one offset per row
    pos = off_stripOffsets;
    for (let row = 0; row < height; row++) {
      wU32(imageDataOffset + row * bytesPerRow);
    }

    // StripByteCounts: constant (width * 3) per strip
    pos = off_stripByteCounts;
    for (let row = 0; row < height; row++) {
      wU32(stripByteCount);
    }

    // ── Image data ────────────────────────────────────────────────────────
    bytes.set(rgb, imageDataOffset);

    return buffer;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Utilities
  // ─────────────────────────────────────────────────────────────────────────────

  /** Drop alpha channel: RGBA → RGB */
  function rgbaToRgb(rgba, width, height) {
    const n   = width * height;
    const rgb = new Uint8Array(n * 3);
    for (let i = 0; i < n; i++) {
      rgb[i * 3]     = rgba[i * 4];
      rgb[i * 3 + 1] = rgba[i * 4 + 1];
      rgb[i * 3 + 2] = rgba[i * 4 + 2];
    }
    return rgb;
  }

  /**
   * Trigger a file download in the browser.
   * @param {ArrayBuffer} buffer  File contents.
   * @param {string}      name    Suggested filename.
   * @param {string}      mime    MIME type.
   */
  function downloadBuffer(buffer, name, mime = 'image/tiff') {
    const blob = new Blob([buffer], { type: mime });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 2000);
  }

  /**
   * Build an ESRI World File (.pgw / .tfw) string.
   * The world file stores the same affine transform as a 6-line text file.
   * Many desktop GIS tools accept PNG + world file as an alternative to GeoTIFF.
   *
   * Line meanings:
   *   1: pixel width  (degrees per pixel in X direction)
   *   2: rotation about Y axis (0 for north-up)
   *   3: rotation about X axis (0 for north-up)
   *   4: pixel height (NEGATIVE degrees per pixel in Y direction)
   *   5: X coordinate of centre of upper-left pixel (west + pixelScaleX/2)
   *   6: Y coordinate of centre of upper-left pixel (north - pixelScaleY/2)
   */
  function buildWorldFile(west, north, east, south, width, height) {
    const pixelScaleX =  (east  - west)  / width;
    const pixelScaleY = -(north - south) / height; // negative = Y increases downward
    // Centre of upper-left pixel
    const ulX = west  + pixelScaleX / 2;
    const ulY = north + pixelScaleY / 2; // pixelScaleY is already negative
    return [
      pixelScaleX.toFixed(10),
      '0.0000000000',
      '0.0000000000',
      pixelScaleY.toFixed(10),
      ulX.toFixed(10),
      ulY.toFixed(10),
    ].join('\n');
  }

  return { write, downloadBuffer, buildWorldFile, rgbaToRgb };

})();
