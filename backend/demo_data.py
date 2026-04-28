"""
Demo data for PeruRE client presentations.
Seeds realistic Lima real estate properties, clients, and tour routes
into the local SQLite database used when PostgreSQL is not available.
"""

import json
import os
import sqlite3
from datetime import date, timedelta
from typing import Optional

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "peru_re_demo.db")


DEMO_PROPERTIES = [
    {
        "id": "prop-001",
        "titulo": "Departamento Moderno en Miraflores",
        "distrito": "Miraflores",
        "tipo": "Departamento",
        "habitaciones": 2,
        "banos": 2,
        "area_m2": 85,
        "precio_soles": 450000,
        "precio_display": "S/ 450,000",
        "direccion": "Av. Larco 1240, Miraflores, Lima",
        "lat": -12.1219,
        "lng": -77.0293,
        "descripcion": "Luminoso departamento con vista al malecón, cocina americana y estacionamiento incluido. A 3 cuadras del parque Kennedy.",
        "amenidades": ["Estacionamiento", "Gimnasio", "Seguridad 24h", "Vista al mar"],
        "estado": "Disponible",
        "foto_url": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=400&h=300&fit=crop",
    },
    {
        "id": "prop-002",
        "titulo": "Casa Colonial en Barranco",
        "distrito": "Barranco",
        "tipo": "Casa",
        "habitaciones": 3,
        "banos": 2,
        "area_m2": 210,
        "precio_soles": 680000,
        "precio_display": "S/ 680,000",
        "direccion": "Jr. Unión 345, Barranco, Lima",
        "lat": -12.1499,
        "lng": -77.0221,
        "descripcion": "Casa republicana restaurada con jardín privado, techos altos y vigas de madera originales. Ideal para familia o galería de arte.",
        "amenidades": ["Jardín", "Terraza", "Cochera doble", "Cuarto de servicio"],
        "estado": "Disponible",
        "foto_url": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=400&h=300&fit=crop",
    },
    {
        "id": "prop-003",
        "titulo": "Penthouse en San Isidro",
        "distrito": "San Isidro",
        "tipo": "Penthouse",
        "habitaciones": 3,
        "banos": 3,
        "area_m2": 180,
        "precio_soles": 1200000,
        "precio_display": "S/ 1,200,000",
        "direccion": "Av. Javier Prado Oeste 1500, San Isidro, Lima",
        "lat": -12.0934,
        "lng": -77.0289,
        "descripcion": "Penthouse de lujo con terraza privada de 60m², vista panorámica a Lima, cocina de chef y acabados importados.",
        "amenidades": ["Terraza privada", "Jacuzzi", "Bodega de vinos", "Concierge", "2 estacionamientos"],
        "estado": "Disponible",
        "foto_url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=400&h=300&fit=crop",
    },
    {
        "id": "prop-004",
        "titulo": "Casa Familiar en La Molina",
        "distrito": "La Molina",
        "tipo": "Casa",
        "habitaciones": 4,
        "banos": 3,
        "area_m2": 320,
        "precio_soles": 750000,
        "precio_display": "S/ 750,000",
        "direccion": "Calle Los Faisanes 280, La Molina, Lima",
        "lat": -12.0847,
        "lng": -76.9388,
        "descripcion": "Amplia casa en condominio cerrado con piscina comunitaria, área verde y colegio a 5 minutos. Perfecta para familia con niños.",
        "amenidades": ["Piscina", "Jardín propio", "Cochera triple", "Cuarto de servicio", "Quincho"],
        "estado": "Disponible",
        "foto_url": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400&h=300&fit=crop",
    },
    {
        "id": "prop-005",
        "titulo": "Studio Moderno en Surco",
        "distrito": "Surco",
        "tipo": "Studio",
        "habitaciones": 1,
        "banos": 1,
        "area_m2": 42,
        "precio_soles": 280000,
        "precio_display": "S/ 280,000",
        "direccion": "Av. Caminos del Inca 1820, Surco, Lima",
        "lat": -12.1388,
        "lng": -76.9716,
        "descripcion": "Studio inteligente con diseño de autor, cocina equipada y balcón. Edificio con rooftop, co-working y lavandería.",
        "amenidades": ["Rooftop", "Co-working", "Lavandería", "Bicicletas compartidas"],
        "estado": "Disponible",
        "foto_url": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=400&h=300&fit=crop",
    },
]

DEMO_CLIENTS = [
    {
        "id": "cli-001",
        "nombre": "María García",
        "telefono": "+51 987 654 321",
        "email": "maria.garcia@email.com",
        "tipo": "Compradora",
        "presupuesto_max": 500000,
        "presupuesto_display": "S/ 500,000",
        "distritos_interes": ["Miraflores", "San Isidro", "Barranco"],
        "habitaciones_min": 2,
        "estado": "En Tour",
        "estado_color": "#f59e0b",
        "fuente": "Referido",
        "notas": "Busca departamento céntrico, viaja por trabajo. Aprobación BCP por S/ 380,000.",
        "propiedades_interes": ["prop-001", "prop-003"],
        "ultima_interaccion": "Hoy, 09:30",
    },
    {
        "id": "cli-002",
        "nombre": "Carlos Ríos",
        "telefono": "+51 976 543 210",
        "email": "carlos.rios@empresa.pe",
        "tipo": "Inversionista",
        "presupuesto_max": 1500000,
        "presupuesto_display": "S/ 1,500,000",
        "distritos_interes": ["San Isidro", "Miraflores", "La Molina"],
        "habitaciones_min": 3,
        "estado": "Negociación",
        "estado_color": "#10b981",
        "fuente": "LinkedIn",
        "notas": "Portfolio de 3 propiedades. Busca rentabilidad >6% anual. Paga al contado.",
        "propiedades_interes": ["prop-003", "prop-004"],
        "ultima_interaccion": "Ayer, 16:00",
    },
    {
        "id": "cli-003",
        "nombre": "Lucía Flores",
        "telefono": "+51 965 432 109",
        "email": "lucia.flores@gmail.com",
        "tipo": "Primera Vivienda",
        "presupuesto_max": 320000,
        "presupuesto_display": "S/ 320,000",
        "distritos_interes": ["Surco", "La Molina", "San Borja"],
        "habitaciones_min": 1,
        "estado": "Nuevo",
        "estado_color": "#38bdf8",
        "fuente": "Instagram",
        "notas": "Primera compra. Necesita orientación sobre Fondo MiVivienda. Trabaja en Surco.",
        "propiedades_interes": ["prop-005"],
        "ultima_interaccion": "Hoy, 11:15",
    },
]

def _tour_date(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")

DEMO_TOURS = [
    {
        "id": "tour-001",
        "fecha": _tour_date(0),
        "fecha_display": "Hoy",
        "cliente_id": "cli-001",
        "cliente_nombre": "María García",
        "paradas": [
            {
                "orden": 1,
                "propiedad_id": "prop-001",
                "propiedad": "Departamento Moderno en Miraflores",
                "direccion": "Av. Larco 1240, Miraflores",
                "hora": "10:00",
                "duracion_min": 45,
                "lat": -12.1219,
                "lng": -77.0293,
            },
            {
                "orden": 2,
                "propiedad_id": "prop-002",
                "propiedad": "Casa Colonial en Barranco",
                "direccion": "Jr. Unión 345, Barranco",
                "hora": "11:30",
                "duracion_min": 60,
                "lat": -12.1499,
                "lng": -77.0221,
            },
        ],
        "inicio_lat": -12.0464,
        "inicio_lng": -77.0428,
        "inicio_nombre": "Oficina PeruRE (Lima Centro)",
        "tiempo_total_min": 150,
        "distancia_km": 18.4,
        "estado": "Confirmado",
    },
    {
        "id": "tour-002",
        "fecha": _tour_date(1),
        "fecha_display": "Mañana",
        "cliente_id": "cli-002",
        "cliente_nombre": "Carlos Ríos",
        "paradas": [
            {
                "orden": 1,
                "propiedad_id": "prop-003",
                "propiedad": "Penthouse en San Isidro",
                "direccion": "Av. Javier Prado Oeste 1500, San Isidro",
                "hora": "10:00",
                "duracion_min": 60,
                "lat": -12.0934,
                "lng": -77.0289,
            },
            {
                "orden": 2,
                "propiedad_id": "prop-004",
                "propiedad": "Casa Familiar en La Molina",
                "direccion": "Calle Los Faisanes 280, La Molina",
                "hora": "12:00",
                "duracion_min": 75,
                "lat": -12.0847,
                "lng": -76.9388,
            },
        ],
        "inicio_lat": -12.0464,
        "inicio_lng": -77.0428,
        "inicio_nombre": "Oficina PeruRE (Lima Centro)",
        "tiempo_total_min": 195,
        "distancia_km": 32.1,
        "estado": "Confirmado",
    },
]


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_properties (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_clients (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demo_tours (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.commit()


def seed_demo_data(db_path: Optional[str] = None) -> dict:
    conn = _get_connection(db_path)
    _ensure_tables(conn)

    for prop in DEMO_PROPERTIES:
        conn.execute(
            "INSERT OR IGNORE INTO demo_properties (id, data) VALUES (?, ?)",
            (prop["id"], json.dumps(prop, ensure_ascii=False)),
        )
    for client in DEMO_CLIENTS:
        conn.execute(
            "INSERT OR IGNORE INTO demo_clients (id, data) VALUES (?, ?)",
            (client["id"], json.dumps(client, ensure_ascii=False)),
        )
    for tour in DEMO_TOURS:
        conn.execute(
            "INSERT OR IGNORE INTO demo_tours (id, data) VALUES (?, ?)",
            (tour["id"], json.dumps(tour, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "propiedades_sembradas": len(DEMO_PROPERTIES),
        "clientes_sembrados": len(DEMO_CLIENTS),
        "tours_sembrados": len(DEMO_TOURS),
    }


def reset_demo_data(db_path: Optional[str] = None) -> dict:
    conn = _get_connection(db_path)
    _ensure_tables(conn)
    conn.execute("DELETE FROM demo_properties")
    conn.execute("DELETE FROM demo_clients")
    conn.execute("DELETE FROM demo_tours")
    conn.commit()
    conn.close()
    return seed_demo_data(db_path)


def get_demo_properties(db_path: Optional[str] = None) -> list:
    conn = _get_connection(db_path)
    _ensure_tables(conn)
    rows = conn.execute("SELECT data FROM demo_properties ORDER BY rowid").fetchall()
    conn.close()
    return [json.loads(r["data"]) for r in rows]


def get_demo_clients(db_path: Optional[str] = None) -> list:
    conn = _get_connection(db_path)
    _ensure_tables(conn)
    rows = conn.execute("SELECT data FROM demo_clients ORDER BY rowid").fetchall()
    conn.close()
    return [json.loads(r["data"]) for r in rows]


def get_demo_tours(db_path: Optional[str] = None) -> list:
    conn = _get_connection(db_path)
    _ensure_tables(conn)
    rows = conn.execute("SELECT data FROM demo_tours ORDER BY rowid").fetchall()
    conn.close()
    return [json.loads(r["data"]) for r in rows]
