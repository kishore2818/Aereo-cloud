import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_root():
    """Verify health and root endpoints"""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "endpoints" in res_root.json()

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


def test_upload_and_measure_kml():
    """
    Test uploading a KML file with mixed geometries:
    - 1 Polygon
    - 1 LineString
    - 1 Point
    """
    with open("samples/survey_sample.kml", "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/files/",
        files={"file": ("survey_sample.kml", file_bytes, "application/vnd.google-earth.kml+xml")}
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    file_id = data["id"]
    assert data["filename"] == "survey_sample.kml"
    assert data["feature_count"] == 3
    assert "4326" in data["crs"]
    assert data["status"] == "COMPLETED"

    # Verify GET /api/files/{id}/
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 3
    assert info_data["status"] == "COMPLETED"
    assert "EPSG:32643" in info_data["projected_crs"]  # Optimal UTM Zone 43N for Bangalore

    # Verify GET /api/files/{id}/measurements/
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["file_id"] == file_id
    assert meas_data["total_features"] == 3
    assert "EPSG:32643" in meas_data["projected_crs"]

    features = meas_data["features"]
    assert len(features) == 3

    # 1. Polygon Feature Check
    poly_feat = next(f for f in features if f["geometry_type"] == "Polygon")
    assert poly_feat["measurement_type"] == "area"
    assert poly_feat["measurements"] is not None
    assert poly_feat["measurements"]["area_sq_meters"] > 100000.0  # Approx 300,000 m²
    assert poly_feat["measurements"]["area_hectares"] > 10.0
    assert poly_feat["measurements"]["perimeter_meters"] > 1000.0

    # 2. LineString Feature Check
    line_feat = next(f for f in features if f["geometry_type"] == "LineString")
    assert line_feat["measurement_type"] == "length"
    assert line_feat["measurements"] is not None
    assert line_feat["measurements"]["length_meters"] > 500.0
    assert line_feat["measurements"]["length_km"] > 0.5

    # 3. Point Feature Check (Gracefully handled)
    point_feat = next(f for f in features if f["geometry_type"] == "Point")
    assert point_feat["measurement_type"] == "none"
    assert point_feat["measurements"] is None
    assert "do not have area or length" in point_feat["note"]

    # Verify Summary totals
    summary = meas_data["summary"]
    assert summary["polygons_measured"] == 1
    assert summary["linestrings_measured"] == 1
    assert summary["points_handled"] == 1
    assert summary["total_area_sq_m"] == poly_feat["measurements"]["area_sq_meters"]
    assert summary["total_length_m"] == line_feat["measurements"]["length_meters"]


def test_upload_and_measure_shapefile_zip():
    """
    Test uploading a Shapefile ZIP containing Polygon parcels.
    """
    with open("samples/parcels_sample.zip", "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/files/",
        files={"file": ("parcels_sample.zip", file_bytes, "application/zip")}
    )
    assert response.status_code == 201
    data = response.json()
    file_id = data["id"]
    assert data["feature_count"] == 2
    assert data["status"] == "COMPLETED"

    # Check measurements
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["summary"]["polygons_measured"] == 2
    assert meas_data["summary"]["total_area_hectares"] > 10.0

    # Properties are preserved
    props = meas_data["features"][0]["properties"]
    assert "parcel_id" in props or "zone" in props


def test_upload_linestring_shapefile():
    """
    Test uploading a Shapefile ZIP containing LineString flight transects.
    """
    with open("samples/flight_paths_sample.zip", "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/files/",
        files={"file": ("flight_paths_sample.zip", file_bytes, "application/zip")}
    )
    assert response.status_code == 201
    file_id = response.json()["id"]

    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["summary"]["linestrings_measured"] == 2
    assert meas_data["summary"]["total_length_m"] > 1000.0


def test_invalid_file_extension():
    """Verify rejection of invalid file extensions"""
    fake_txt = io.BytesIO(b"Hello world, not a GIS file")
    response = client.post(
        "/api/files/",
        files={"file": ("invalid.txt", fake_txt, "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_corrupted_or_empty_zip():
    """Verify error handling on zip without shapefiles"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("notes.txt", "No shapefile inside")
    zip_buffer.seek(0)

    response = client.post(
        "/api/files/",
        files={"file": ("bad_archive.zip", zip_buffer.getvalue(), "application/zip")}
    )
    assert response.status_code == 400
    assert "No '.shp' file found" in response.json()["detail"]


def test_file_not_found():
    """Verify 404 responses for nonexistent IDs"""
    res_info = client.get("/api/files/nonexistent-id/")
    assert res_info.status_code == 404

    res_meas = client.get("/api/files/nonexistent-id/measurements/")
    assert res_meas.status_code == 404


def test_list_all_files():
    """Verify listing all uploaded files"""
    res = client.get("/api/files/")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) >= 2
