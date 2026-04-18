from __future__ import annotations

from pydantic import BaseModel, Field


class CropSpec(BaseModel):
    rotation_quadrants: int = Field(default=0, ge=0, le=3)
    crop_x: int = Field(ge=0)
    crop_y: int = Field(ge=0)
    crop_width: int = Field(gt=0)
    crop_height: int = Field(gt=0)


class AssetCropDraftCreate(CropSpec):
    folder: str | None = None
