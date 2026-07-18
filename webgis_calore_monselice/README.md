# Monselice — mappa del calore urbano (webGIS statico)

Pagina Leaflet completamente statica: nessun GeoServer, nessun backend.
I GeoTIFF vengono caricati e renderizzati nel browser (georaster +
georaster-layer-for-leaflet); il click legge il valore vero del pixel e lo
spiega con frasi di contesto basate sulle statistiche precalcolate.

## Struttura

```
webgis_sottosuoli/
├── index.html              # tutta la pagina: UI, config, logica
└── dati/
    ├── lst_giugno2026.tif        ┐
    ├── anomalia_giugno2026.tif   │ 8 raster EPSG:4326, Float32,
    ├── ndvi_giugno2026.tif       │ deflate, nodata = -9999
    ├── ndbi_giugno2026.tif       │ (~85–100 KB l'uno)
    ├── lst_mediana2226.tif       │
    ├── anomalia_mediana2226.tif  │
    ├── ndvi_mediana2226.tif      │
    ├── ndbi_mediana2226.tif      ┘
    ├── sezioni.geojson           # 259 sezioni ISTAT, attributi whitelisted
    └── statistiche.json          # min/max/media/percentili per raster
```

## Test in locale

I browser bloccano `fetch()` da `file://`, quindi serve un server locale:

```bash
cd webgis_sottosuoli
python3 -m http.server 8000
# poi apri http://localhost:8000
```

## Deploy su GitHub Pages

Copia la cartella nel repo del sito (es. `calore-monselice/`) e committa:
la pagina sarà su `https://andrearosina.com/calore-monselice/`.
Tutti i percorsi sono relativi, quindi funziona in qualunque sottocartella.

## Da personalizzare

- **Link all'articolo**: in `index.html` cerca `ARTICLE_URL` (in cima alla
  configurazione) e sostituisci con l'URL del pezzo.
- **Testi esplicativi**: tutte le descrizioni (ⓘ dei layer, frasi di
  interpretazione, guida) sono nella sezione CONFIGURAZIONE e nelle funzioni
  `interpret*` / `guideHTML` di `index.html`. Nessun testo è sparso nel markup.
- **Palette e scale**: nell'oggetto `VARS`. `domain: [min, max]` = scala
  fissa; `domain: "p2p98"` = stiramento sui percentili 2–98 del raster.

## Aggiornare o aggiungere dati

I file in `dati/` sono derivati (EPSG:4326, nodata, statistiche): non
sostituirli direttamente con export GEE/QGIS in UTM. Per rigenerarli da
nuovi export usare lo stesso procedimento (riproiezione in EPSG:4326 con
nodata -9999 e compressione deflate **senza predictor**, più il ricalcolo
di `statistiche.json` con i 101 percentili per raster). Per un nuovo layer:
preparare il tif, aggiungere la voce in `VARS` (o un nuovo periodo in
`PERIODS`) e la relativa entry nelle statistiche.

## Crediti dati

Landsat 8/9 Collection 2 (USGS/NASA) via Google Earth Engine ·
geometrie e censimento ISTAT 2021/2023 · elaborazione Andrea Rosina.
