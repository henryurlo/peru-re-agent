"""
Demo API router for PeruRE client presentations.
Provides seed/reset endpoints and structured JSON for demo properties,
clients, and tours — all with Spanish labels.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.demo_data import (
    get_demo_clients,
    get_demo_properties,
    get_demo_tours,
    reset_demo_data,
    seed_demo_data,
)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/seed")
async def seed():
    """Inserta datos demo si aún no existen."""
    result = seed_demo_data()
    return JSONResponse(content=result)


@router.post("/reset")
async def reset():
    """Elimina todos los datos demo y los re-inserta frescos."""
    result = reset_demo_data()
    return JSONResponse(content=result)


@router.get("/properties")
async def properties():
    """Retorna las 5 propiedades demo de Lima."""
    props = get_demo_properties()
    return JSONResponse(content={
        "status": "success",
        "total": len(props),
        "propiedades": props,
    })


@router.get("/clients")
async def clients():
    """Retorna los 3 clientes demo."""
    clts = get_demo_clients()
    return JSONResponse(content={
        "status": "success",
        "total": len(clts),
        "clientes": clts,
    })


@router.get("/tours")
async def tours():
    """Retorna los tours programados para hoy y mañana."""
    trrs = get_demo_tours()
    return JSONResponse(content={
        "status": "success",
        "total": len(trrs),
        "tours": trrs,
    })
