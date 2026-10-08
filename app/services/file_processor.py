import os
import shutil
import uuid
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.services.crs_service import CRSService
from app.services.measurement import MeasurementService


class FileProcessor:
    """
    Handles file validation, extraction, geospatial loading (Shapefile / KML),
    CRS reprojection, and measurement computations.
    """

    def __init__(self):
        self.storage_dir = settings.UPLOAD_DIR
        self.metadata_file = self.storage_dir / "registry.json"
        self._registry: Dict[str, Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_registry(self) -> None:
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to persist registry to disk: {e}")

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        record = self._registry.get(file_id)
        if not record:
            return None
        return record.get("info")

    def get_measurements(self, file_id: str) -> Optional[Dict[str, Any]]:
        record = self._registry.get(file_id)
        if not record:
            return None
        return record.get("measurements")

    def list_files(self) -> list:
        return [record["info"] for record in self._registry.values() if "info" in record]

    async def process_uploaded_file(self, file: UploadFile) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        file_id = str(uuid.uuid4())[:8]
        file_work_dir = self.storage_dir / file_id
        file_work_dir.mkdir(parents=True, exist_ok=True)
        saved_file_path = file_work_dir / filename

        # Stream file to disk
        try:
            with open(saved_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

        # Process geospatial data
        try:
            if ext == ".zip":
                gdf = self._load_shapefile_from_zip(saved_file_path, file_work_dir)
            elif ext == ".kml":
                gdf = self._load_kml(saved_file_path)
            else:
                raise HTTPException(status_code=400, detail="Unsupported file format.")

            if gdf is None or len(gdf) == 0:
                raise HTTPException(status_code=400, detail="The file does not contain any valid geospatial features.")

            # Reproject to metric projected coordinate system (e.g. UTM)
            projected_gdf, source_crs, target_crs = CRSService.reproject_for_measurement(gdf)

            # Compute measurements
            measurements = MeasurementService.calculate_measurements(
                source_gdf=gdf,
                projected_gdf=projected_gdf,
                source_crs=source_crs,
                projected_crs=target_crs,
                file_id=file_id,
                filename=filename
            )

            file_info = {
                "id": file_id,
                "filename": filename,
                "file_type": ext,
                "feature_count": len(gdf),
                "crs": source_crs,
                "projected_crs": target_crs,
                "status": "COMPLETED",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message": f"Successfully processed {len(gdf)} features with CRS projection to {target_crs}."
            }

            # Store in registry
            self._registry[file_id] = {
                "info": file_info,
                "measurements": measurements
            }
            self._save_registry()

            return file_info, measurements

        except HTTPException:
            raise
        except Exception as e:
            file_info = {
                "id": file_id,
                "filename": filename,
                "file_type": ext,
                "feature_count": 0,
                "crs": "UNKNOWN",
                "status": "FAILED",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
            self._registry[file_id] = {"info": file_info, "measurements": None}
            self._save_registry()
            raise HTTPException(status_code=422, detail=f"Failed to process geospatial file: {str(e)}")

    def _load_shapefile_from_zip(self, zip_path: Path, work_dir: Path) -> gpd.GeoDataFrame:
        """
        Extracts zip archive and verifies required shapefile components (.shp, .shx, .dbf).
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Check for zip slip
                for member in zf.namelist():
                    resolved = (work_dir / member).resolve()
                    if not str(resolved).startswith(str(work_dir.resolve())):
                        raise ValueError("Security error: Zip archive contains illegal directory traversal paths.")
                zf.extractall(work_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="The uploaded zip file is corrupted or invalid.")

        # Find .shp files
        shp_files = list(work_dir.rglob("*.shp"))
        if not shp_files:
            raise HTTPException(
                status_code=400, 
                detail="Invalid Shapefile zip archive: No '.shp' file found inside the package."
            )

        shp_file = shp_files[0]
        # Verify required companion files exist (.shx, .dbf)
        stem = shp_file.stem
        parent = shp_file.parent
        has_shx = (parent / f"{stem}.shx").exists() or (parent / f"{stem}.SHX").exists()
        has_dbf = (parent / f"{stem}.dbf").exists() or (parent / f"{stem}.DBF").exists()

        if not has_shx or not has_dbf:
            raise HTTPException(
                status_code=400,
                detail=f"Incomplete Shapefile: Missing required companion files (expected '{stem}.shx' and '{stem}.dbf')."
            )

        try:
            gdf = gpd.read_file(shp_file)
            return gdf
        except Exception as e:
            raise ValueError(f"Could not read shapefile: {str(e)}")

    def _load_kml(self, kml_path: Path) -> gpd.GeoDataFrame:
        """
        Reads KML files using pyogrio/geopandas with a fallback XML parser.
        """
        # Try native driver first
        try:
            gdf = gpd.read_file(kml_path)
            if gdf is not None and len(gdf) > 0:
                if gdf.crs is None:
                    gdf = gdf.set_crs(CRSService.DEFAULT_GEOGRAPHIC_CRS)
                return gdf
        except Exception:
            pass

        # Robust Fallback XML Parser for KML Placemarks
        return self._parse_kml_xml(kml_path)

    def _parse_kml_xml(self, kml_path: Path) -> gpd.GeoDataFrame:
        """
        Zero-dependency fallback XML parser for KML geometries.
        Handles Placemark elements containing Polygon, LineString, and Point.
        """
        try:
            tree = ET.parse(kml_path)
            root = tree.getroot()
        except Exception as e:
            raise ValueError(f"Invalid or corrupted XML/KML content: {str(e)}")

        records = []
        geometries = []

        # Remove XML namespace prefix if present
        def clean_tag(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        def parse_coord_str(text: str) -> list:
            coords = []
            tuples = text.strip().split()
            for t in tuples:
                parts = [float(p) for p in t.split(",") if p.strip()]
                if len(parts) >= 2:
                    coords.append((parts[0], parts[1]))
            return coords

        for elem in root.iter():
            if clean_tag(elem.tag) == "Placemark":
                props = {}
                geom = None

                for child in elem:
                    tag_name = clean_tag(child.tag)
                    if tag_name in ["name", "description"]:
                        props[tag_name] = child.text
                    elif tag_name == "Point":
                        for sub in child:
                            if clean_tag(sub.tag) == "coordinates" and sub.text:
                                c = parse_coord_str(sub.text)
                                if c:
                                    geom = Point(c[0])
                    elif tag_name == "LineString":
                        for sub in child:
                            if clean_tag(sub.tag) == "coordinates" and sub.text:
                                c = parse_coord_str(sub.text)
                                if len(c) >= 2:
                                    geom = LineString(c)
                    elif tag_name == "Polygon":
                        outer_coords = []
                        for sub in child.iter():
                            if clean_tag(sub.tag) == "coordinates" and sub.text:
                                c = parse_coord_str(sub.text)
                                if len(c) >= 3:
                                    outer_coords = c
                                    break
                        if outer_coords:
                            geom = Polygon(outer_coords)

                if geom is not None:
                    records.append(props)
                    geometries.append(geom)

        if not geometries:
            raise ValueError("No recognizable Polygon, LineString, or Point placemarks found in the KML file.")

        gdf = gpd.GeoDataFrame(records, geometry=geometries, crs=CRSService.DEFAULT_GEOGRAPHIC_CRS)
        return gdf


# Singleton instance
file_processor = FileProcessor()
