from typing import Any, Dict, List, Tuple
from shapely.geometry import mapping
import geopandas as gpd

class MeasurementService:
    """
    Computes spatial measurements for features based on geometry types:
    - Polygon / MultiPolygon -> Area (m², ha, km²) and Perimeter (m)
    - LineString / MultiLineString -> Length (m, km)
    - Point / MultiPoint -> Gracefully ignored with explicit note
    - Others / Invalid -> Gracefully handled without raising exceptions
    """

    @classmethod
    def calculate_measurements(
        cls, 
        source_gdf: gpd.GeoDataFrame, 
        projected_gdf: gpd.GeoDataFrame,
        source_crs: str,
        projected_crs: str,
        file_id: str,
        filename: str
    ) -> Dict[str, Any]:
        feature_items: List[Dict[str, Any]] = []

        total_area_sq_m = 0.0
        total_length_m = 0.0
        polygons_measured = 0
        linestrings_measured = 0
        points_handled = 0
        unsupported_features = 0

        # Iterate over each feature row
        for idx in range(len(source_gdf)):
            source_row = source_gdf.iloc[idx]
            proj_row = projected_gdf.iloc[idx]

            source_geom = source_row.geometry
            proj_geom = proj_row.geometry

            # Extract non-geometry attributes/properties
            properties = {}
            for col in source_gdf.columns:
                if col != source_gdf.geometry.name:
                    val = source_row[col]
                    val_str = str(val).strip().lower()
                    if val is not None and val_str not in ["nan", "nat", "<na>", "none", ""]:
                        properties[col] = val if isinstance(val, (int, float, str, bool)) else str(val)

            geom_type = proj_geom.geom_type if proj_geom is not None else "Unknown"
            
            # Convert source geometry to GeoJSON for client visualization
            geojson_geom = None
            if source_geom is not None and not source_geom.is_empty:
                try:
                    geojson_geom = mapping(source_geom)
                except Exception:
                    geojson_geom = None

            # 1. Polygon / MultiPolygon -> Area
            if geom_type in ["Polygon", "MultiPolygon"]:
                if proj_geom is not None and not proj_geom.is_empty:
                    area_sq_m = round(float(proj_geom.area), 2)
                    perimeter_m = round(float(proj_geom.length), 2)
                    area_ha = round(area_sq_m / 10000.0, 4)
                    area_sq_km = round(area_sq_m / 1_000_000.0, 6)

                    total_area_sq_m += area_sq_m
                    polygons_measured += 1

                    feature_items.append({
                        "feature_id": idx,
                        "geometry_type": geom_type,
                        "measurement_type": "area",
                        "measurements": {
                            "area_sq_meters": area_sq_m,
                            "area_hectares": area_ha,
                            "area_sq_km": area_sq_km,
                            "perimeter_meters": perimeter_m
                        },
                        "properties": properties,
                        "geometry_geojson": geojson_geom,
                        "note": None
                    })
                else:
                    unsupported_features += 1
                    feature_items.append({
                        "feature_id": idx,
                        "geometry_type": geom_type,
                        "measurement_type": "area",
                        "measurements": None,
                        "properties": properties,
                        "geometry_geojson": geojson_geom,
                        "note": "Empty or corrupted Polygon geometry"
                    })

            # 2. LineString / MultiLineString -> Length
            elif geom_type in ["LineString", "MultiLineString"]:
                if proj_geom is not None and not proj_geom.is_empty:
                    length_m = round(float(proj_geom.length), 2)
                    length_km = round(length_m / 1000.0, 4)

                    total_length_m += length_m
                    linestrings_measured += 1

                    feature_items.append({
                        "feature_id": idx,
                        "geometry_type": geom_type,
                        "measurement_type": "length",
                        "measurements": {
                            "length_meters": length_m,
                            "length_km": length_km
                        },
                        "properties": properties,
                        "geometry_geojson": geojson_geom,
                        "note": None
                    })
                else:
                    unsupported_features += 1
                    feature_items.append({
                        "feature_id": idx,
                        "geometry_type": geom_type,
                        "measurement_type": "length",
                        "measurements": None,
                        "properties": properties,
                        "geometry_geojson": geojson_geom,
                        "note": "Empty or corrupted LineString geometry"
                    })

            # 3. Point / MultiPoint -> No measurement required
            elif geom_type in ["Point", "MultiPoint"]:
                points_handled += 1
                feature_items.append({
                    "feature_id": idx,
                    "geometry_type": geom_type,
                    "measurement_type": "none",
                    "measurements": None,
                    "properties": properties,
                    "geometry_geojson": geojson_geom,
                    "note": "Point geometries do not have area or length measurements."
                })

            # 4. Other / GeometryCollection / Unsupported
            else:
                unsupported_features += 1
                feature_items.append({
                    "feature_id": idx,
                    "geometry_type": geom_type,
                    "measurement_type": "unsupported",
                    "measurements": None,
                    "properties": properties,
                    "geometry_geojson": geojson_geom,
                    "note": f"Geometry type '{geom_type}' is not supported for measurement calculation."
                })

        summary = {
            "total_features": len(source_gdf),
            "polygons_measured": polygons_measured,
            "linestrings_measured": linestrings_measured,
            "points_handled": points_handled,
            "unsupported_features": unsupported_features,
            "total_area_sq_m": round(total_area_sq_m, 2),
            "total_area_hectares": round(total_area_sq_m / 10000.0, 4),
            "total_length_m": round(total_length_m, 2),
            "total_length_km": round(total_length_m / 1000.0, 4)
        }

        return {
            "file_id": file_id,
            "filename": filename,
            "source_crs": source_crs,
            "projected_crs": projected_crs,
            "total_features": len(source_gdf),
            "summary": summary,
            "features": feature_items
        }
