from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class FileUploadResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Detected file type (.zip or .kml)")
    feature_count: int = Field(..., description="Total number of extracted features")
    crs: str = Field(..., description="Source Coordinate Reference System")
    status: str = Field(..., description="Processing status (COMPLETED, FAILED)")
    message: str = Field(..., description="Status description")

class FileInfoResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    feature_count: int = Field(..., description="Number of geospatial features")
    crs: str = Field(..., description="Source Coordinate Reference System")
    status: str = Field(..., description="Processing status")
    projected_crs: Optional[str] = Field(None, description="Target projected CRS used for metric measurements")
    created_at: Optional[str] = Field(None, description="Upload timestamp")

class PolygonMeasurements(BaseModel):
    area_sq_meters: float = Field(..., description="Area in square meters (m²)")
    area_hectares: float = Field(..., description="Area in hectares (ha)")
    area_sq_km: float = Field(..., description="Area in square kilometers (km²)")
    perimeter_meters: float = Field(..., description="Perimeter in meters (m)")

class LineStringMeasurements(BaseModel):
    length_meters: float = Field(..., description="Length in meters (m)")
    length_km: float = Field(..., description="Length in kilometers (km)")

class FeatureMeasurementItem(BaseModel):
    feature_id: int = Field(..., description="Feature index / ID")
    geometry_type: str = Field(..., description="Geometry type (e.g., Polygon, LineString, Point)")
    measurement_type: str = Field(..., description="Type of measurement computed ('area', 'length', 'none', 'unsupported')")
    measurements: Optional[Dict[str, Any]] = Field(None, description="Calculated metric measurements")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes / properties")
    geometry_geojson: Optional[Dict[str, Any]] = Field(None, description="GeoJSON representation of geometry")
    note: Optional[str] = Field(None, description="Additional context or graceful handling note")

class MeasurementSummary(BaseModel):
    total_features: int
    polygons_measured: int
    linestrings_measured: int
    points_handled: int
    unsupported_features: int
    total_area_sq_m: float
    total_area_hectares: float
    total_length_m: float
    total_length_km: float

class FileMeasurementsResponse(BaseModel):
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    source_crs: str = Field(..., description="Input file CRS (e.g., EPSG:4326)")
    projected_crs: str = Field(..., description="Projected metric CRS used for measurement (e.g., EPSG:32643)")
    total_features: int = Field(..., description="Total number of features processed")
    summary: MeasurementSummary = Field(..., description="Aggregate totals for measurements")
    features: List[FeatureMeasurementItem] = Field(..., description="List of per-feature measurement details")
