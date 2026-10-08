import os
import zipfile
import tempfile
import geopandas as gpd
from shapely.geometry import Polygon, LineString

os.makedirs("samples", exist_ok=True)

# 1. survey_sample.kml is already generated (mixed geometry types: Polygon, LineString, Point)

# 2. Create parcels_sample.zip (Polygon Shapefile)
with tempfile.TemporaryDirectory() as td:
    polygon_records = [
        {
            "parcel_id": "P-101",
            "zone": "Agricultural",
            "geometry": Polygon([
                (77.5850, 12.9650),
                (77.5890, 12.9650),
                (77.5890, 12.9690),
                (77.5850, 12.9690),
                (77.5850, 12.9650)
            ])
        },
        {
            "parcel_id": "P-102",
            "zone": "Commercial",
            "geometry": Polygon([
                (77.5895, 12.9650),
                (77.5935, 12.9650),
                (77.5935, 12.9690),
                (77.5895, 12.9690),
                (77.5895, 12.9650)
            ])
        }
    ]

    gdf_poly = gpd.GeoDataFrame(polygon_records, crs="EPSG:4326")
    shp_base = os.path.join(td, "parcels")
    gdf_poly.to_file(shp_base + ".shp")

    zip_out = "samples/parcels_sample.zip"
    with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            path = shp_base + ext
            if os.path.exists(path):
                zf.write(path, arcname=f"parcels{ext}")

print(f"Created {zip_out}")

# 3. Create flight_paths_sample.zip (LineString Shapefile)
with tempfile.TemporaryDirectory() as td:
    line_records = [
        {
            "flight_id": "FL-001",
            "pilot": "Autonomous Drone",
            "geometry": LineString([
                (77.5840, 12.9640),
                (77.5880, 12.9660),
                (77.5940, 12.9700)
            ])
        },
        {
            "flight_id": "FL-002",
            "pilot": "Manual Return",
            "geometry": LineString([
                (77.5940, 12.9700),
                (77.5950, 12.9720),
                (77.5980, 12.9750)
            ])
        }
    ]

    gdf_lines = gpd.GeoDataFrame(line_records, crs="EPSG:4326")
    shp_base = os.path.join(td, "flight_paths")
    gdf_lines.to_file(shp_base + ".shp")

    zip_out = "samples/flight_paths_sample.zip"
    with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            path = shp_base + ext
            if os.path.exists(path):
                zf.write(path, arcname=f"flight_paths{ext}")

print(f"Created {zip_out}")
