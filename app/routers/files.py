from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.schemas import (
    FileUploadResponse,
    FileInfoResponse,
    FileMeasurementsResponse,
)
from app.services.file_processor import file_processor

router = APIRouter(prefix="/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process geospatial file",
    description="Accepts a `.zip` archive containing an ESRI Shapefile or a `.kml` file. Extracts features, reprojects to a local metric CRS (e.g. UTM), and computes spatial measurements."
)
async def upload_file(file: UploadFile = File(..., description="Geospatial file (.zip or .kml)")):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded or filename is missing.")

    file_info, _ = await file_processor.process_uploaded_file(file)
    return file_info


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
    description="Returns metadata about an uploaded geospatial file including feature count, CRS, and processing status."
)
async def get_file_info(file_id: str):
    info = file_processor.get_file_info(file_id)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )
    return info


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get geospatial measurements",
    description="Returns detailed per-feature spatial measurements (Area for Polygons, Length for LineStrings) calculated in metric units after automatic CRS reprojection."
)
async def get_measurements(file_id: str):
    measurements = file_processor.get_measurements(file_id)
    if not measurements:
        info = file_processor.get_file_info(file_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with ID '{file_id}' not found."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Measurements unavailable for file '{file_id}' (Status: {info.get('status', 'UNKNOWN')})."
        )
    return measurements


@router.get(
    "/",
    response_model=List[FileInfoResponse],
    summary="List all uploaded files",
    description="Returns a list of all uploaded and processed geospatial files."
)
async def list_files():
    return file_processor.list_files()
