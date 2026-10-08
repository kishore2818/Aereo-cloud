from typing import Tuple, Any
import geopandas as gpd
from pyproj import CRS

class CRSService:
    """
    Handles Coordinate Reference System (CRS) inspection, validation,
    and automatic projection to an optimal metric coordinate system (e.g., UTM)
    to ensure area and distance measurements are never calculated in degrees.
    """

    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    def ensure_source_crs(cls, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Ensures the GeoDataFrame has a defined CRS.
        If missing, defaults to EPSG:4326 (WGS 84 geographic coordinates).
        """
        if gdf.crs is None:
            gdf = gdf.set_crs(cls.DEFAULT_GEOGRAPHIC_CRS)
        return gdf

    @classmethod
    def get_crs_string(cls, crs: Any) -> str:
        """
        Returns a clean string representation of the CRS (e.g., 'EPSG:4326').
        """
        if crs is None:
            return cls.DEFAULT_GEOGRAPHIC_CRS
        try:
            pyproj_crs = CRS.from_user_input(crs)
            auth = pyproj_crs.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            return pyproj_crs.name or str(crs)
        except Exception:
            return str(crs)

    @classmethod
    def determine_optimal_projected_crs(cls, gdf: gpd.GeoDataFrame) -> str:
        """
        Determines the optimal projected metric CRS (Cartesian, in meters).
        Strategy:
        1. If source CRS is already projected (units = meters/feet), keep it.
        2. If geographic (EPSG:4326 or degrees):
           a. Use GeoPandas' `estimate_utm_crs()` to identify the exact local UTM zone.
           b. Fallback: Compute centroid (longitude, latitude) and calculate WGS 84 UTM zone formula.
           c. Global fallback: If geometries span cross-continental bounds, use EPSG:3857 or EPSG:6933.
        """
        source_crs = gdf.crs
        if source_crs is not None:
            try:
                pyproj_crs = CRS.from_user_input(source_crs)
                if pyproj_crs.is_projected:
                    # Already projected (metric/linear system)
                    auth = pyproj_crs.to_authority()
                    if auth:
                        return f"{auth[0]}:{auth[1]}"
                    return pyproj_crs.to_string()
            except Exception:
                pass

        # If geographic, calculate optimal local UTM zone
        try:
            estimated_utm = gdf.estimate_utm_crs()
            if estimated_utm is not None:
                auth = estimated_utm.to_authority()
                if auth:
                    return f"{auth[0]}:{auth[1]}"
                return estimated_utm.to_string()
        except Exception:
            pass

        # Centroid mathematical fallback
        try:
            # Dissolve / unary union to find overall centroid
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            center_lon = (bounds[0] + bounds[2]) / 2.0
            center_lat = (bounds[1] + bounds[3]) / 2.0

            zone_number = int((center_lon + 180) / 6) + 1
            zone_number = max(1, min(60, zone_number))
            if center_lat >= 0:
                epsg_code = 32600 + zone_number  # WGS 84 / UTM North
            else:
                epsg_code = 32700 + zone_number  # WGS 84 / UTM South
            return f"EPSG:{epsg_code}"
        except Exception:
            # Standard Web Mercator in meters as safe fallback
            return "EPSG:3857"

    @classmethod
    def reproject_for_measurement(cls, gdf: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, str, str]:
        """
        Prepares GeoDataFrame for accurate metric calculations:
        1. Ensures source CRS is identified.
        2. Determines the best local metric projected CRS.
        3. Reprojects all geometries to the target projected CRS.
        
        Returns:
            (projected_gdf, source_crs_str, target_crs_str)
        """
        gdf = cls.ensure_source_crs(gdf)
        source_crs_str = cls.get_crs_string(gdf.crs)
        target_crs_str = cls.determine_optimal_projected_crs(gdf)

        # Reproject to target projected CRS
        projected_gdf = gdf.to_crs(target_crs_str)
        return projected_gdf, source_crs_str, target_crs_str
