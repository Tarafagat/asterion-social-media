from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends

from packages.config import Settings

from .. import services
from ..deps import get_db_path, get_settings_dep

router = APIRouter(tags=["system"])


def _dir_size_bytes(path: Path) -> int:
    """Suma el tamaño de todo lo que cuelga de `path` (solo metadatos, no
    lee los archivos) — lo que ocupan en disco los datos de este plugin."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass  # un archivo que desaparece a mitad del walk no es error
    return total


@router.get("/storage")
def storage(
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    """Espacio del disco donde viven los datos + cuánto ocupan los
    proyectos de este plugin. Lo usa el panel de Proyectos para avisar
    antes de que se llene el disco."""
    data_dir = settings.data_dir_path()
    data_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(data_dir)
    data_used = _dir_size_bytes(data_dir)
    projects = services.projects.list_projects(db_path)
    return {
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
        "data_used_bytes": data_used,
        "project_count": len(projects),
        "limit_max_storage_gb": settings.limit_max_storage_gb,
        "data_dir": str(data_dir),
    }
