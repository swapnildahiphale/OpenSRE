from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

UI_DIR = Path(__file__).resolve().parents[2] / "ui"


@router.get("/")
def ui_index():
    return FileResponse(UI_DIR / "index.html")


@router.get("/ui/app.js")
def ui_js():
    return FileResponse(UI_DIR / "app.js", media_type="text/javascript")


@router.get("/admin")
def ui_admin():
    return FileResponse(UI_DIR / "admin.html")


@router.get("/ui/admin.js")
def ui_admin_js():
    return FileResponse(UI_DIR / "admin.js", media_type="text/javascript")
