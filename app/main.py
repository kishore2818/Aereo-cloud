from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers.files import router as files_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
### Geospatial File Measurement API

A production-grade backend service built with **FastAPI**, **GeoPandas**, and **Shapely** to ingest, reproject, and calculate precise metric measurements for geospatial vector datasets.

#### Supported Formats:
* **ESRI Shapefile** packaged in `.zip` (must include `.shp`, `.shx`, and `.dbf`)
* **Keyhole Markup Language** (`.kml`)

#### Measurement Capabilities:
* **Polygons / MultiPolygons**: Area ($m^2$, hectares, $km^2$) and Perimeter ($m$)
* **LineStrings / MultiLineStrings**: Length ($m$, $km$)
* **Points / MultiPoints**: Gracefully acknowledged without calculation
* **CRS Reprojection**: Automatic conversion from geographic coordinate systems (e.g. WGS 84 `EPSG:4326`) to optimal local metric projected coordinate systems (e.g. UTM) to prevent degree-based calculation distortion.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes under /api
app.include_router(files_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health & Meta"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "documentation": "/docs",
        "endpoints": {
            "upload": "POST /api/files/",
            "file_info": "GET /api/files/{id}/",
            "measurements": "GET /api/files/{id}/measurements/",
            "list_all": "GET /api/files/"
        }
    }


@app.get("/health", tags=["Health & Meta"])
async def health_check():
    return {"status": "ok", "service": "Geospatial File Measurement API"}
