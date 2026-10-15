from __future__ import annotations

from fastapi import APIRouter, Depends

from packages.config import Settings

from ..deps import get_settings_dep
from ..schemas import SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings_view(settings: Settings = Depends(get_settings_dep)):
    return SettingsOut.from_settings(settings)
