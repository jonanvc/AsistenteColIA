"""
Geographic data for Colombia - Departments and major municipalities.
Simplified GeoJSON for selection purposes.
"""

# Colombia center coordinates
COLOMBIA_CENTER = {
    "lat": 4.5709,
    "lng": -74.2973,
    "zoom": 6
}

# Colombia bounding box
COLOMBIA_BOUNDS = {
    "north": 13.5,
    "south": -4.5,
    "east": -66.5,
    "west": -82.0
}

# Coverage types
COVERAGE_TYPES = {
    "municipal": "Municipal",
    "departmental": "Departamental", 
    "regional": "Regional (varios departamentos)",
    "national": "Nacional"
}

# Departments of Colombia with their capitals and approximate center coordinates
DEPARTMENTS = {
    "amazonas": {"name": "Amazonas", "capital": "Leticia", "lat": -1.0, "lng": -71.5, "code": "91"},
    "antioquia": {"name": "Antioquia", "capital": "Medellín", "lat": 6.7, "lng": -75.5, "code": "05"},
    "arauca": {"name": "Arauca", "capital": "Arauca", "lat": 6.8, "lng": -70.5, "code": "81"},
    "atlantico": {"name": "Atlántico", "capital": "Barranquilla", "lat": 10.7, "lng": -74.9, "code": "08"},
    "bogota": {"name": "Bogotá D.C.", "capital": "Bogotá", "lat": 4.6, "lng": -74.1, "code": "11"},
    "bolivar": {"name": "Bolívar", "capital": "Cartagena", "lat": 8.5, "lng": -74.5, "code": "13"},
    "boyaca": {"name": "Boyacá", "capital": "Tunja", "lat": 5.8, "lng": -73.0, "code": "15"},
    "caldas": {"name": "Caldas", "capital": "Manizales", "lat": 5.3, "lng": -75.5, "code": "17"},
    "caqueta": {"name": "Caquetá", "capital": "Florencia", "lat": 1.0, "lng": -75.0, "code": "18"},
    "casanare": {"name": "Casanare", "capital": "Yopal", "lat": 5.5, "lng": -71.5, "code": "85"},
    "cauca": {"name": "Cauca", "capital": "Popayán", "lat": 2.5, "lng": -76.8, "code": "19"},
    "cesar": {"name": "Cesar", "capital": "Valledupar", "lat": 9.5, "lng": -73.5, "code": "20"},
    "choco": {"name": "Chocó", "capital": "Quibdó", "lat": 6.0, "lng": -77.0, "code": "27"},
    "cordoba": {"name": "Córdoba", "capital": "Montería", "lat": 8.5, "lng": -75.8, "code": "23"},
    "cundinamarca": {"name": "Cundinamarca", "capital": "Bogotá", "lat": 5.0, "lng": -74.0, "code": "25"},
    "guainia": {"name": "Guainía", "capital": "Inírida", "lat": 2.5, "lng": -68.5, "code": "94"},
    "guaviare": {"name": "Guaviare", "capital": "San José del Guaviare", "lat": 2.0, "lng": -72.5, "code": "95"},
    "huila": {"name": "Huila", "capital": "Neiva", "lat": 2.5, "lng": -75.5, "code": "41"},
    "guajira": {"name": "La Guajira", "capital": "Riohacha", "lat": 11.5, "lng": -72.5, "code": "44"},
    "magdalena": {"name": "Magdalena", "capital": "Santa Marta", "lat": 10.5, "lng": -74.2, "code": "47"},
    "meta": {"name": "Meta", "capital": "Villavicencio", "lat": 3.5, "lng": -73.0, "code": "50"},
    "narino": {"name": "Nariño", "capital": "Pasto", "lat": 1.5, "lng": -77.5, "code": "52"},
    "norte_santander": {"name": "Norte de Santander", "capital": "Cúcuta", "lat": 8.0, "lng": -72.8, "code": "54"},
    "putumayo": {"name": "Putumayo", "capital": "Mocoa", "lat": 0.5, "lng": -76.5, "code": "86"},
    "quindio": {"name": "Quindío", "capital": "Armenia", "lat": 4.5, "lng": -75.7, "code": "63"},
    "risaralda": {"name": "Risaralda", "capital": "Pereira", "lat": 5.0, "lng": -75.8, "code": "66"},
    "san_andres": {"name": "San Andrés y Providencia", "capital": "San Andrés", "lat": 12.5, "lng": -81.7, "code": "88"},
    "santander": {"name": "Santander", "capital": "Bucaramanga", "lat": 7.0, "lng": -73.2, "code": "68"},
    "sucre": {"name": "Sucre", "capital": "Sincelejo", "lat": 9.3, "lng": -75.4, "code": "70"},
    "tolima": {"name": "Tolima", "capital": "Ibagué", "lat": 4.0, "lng": -75.2, "code": "73"},
    "valle_cauca": {"name": "Valle del Cauca", "capital": "Cali", "lat": 3.8, "lng": -76.5, "code": "76"},
    "vaupes": {"name": "Vaupés", "capital": "Mitú", "lat": 1.0, "lng": -70.0, "code": "97"},
    "vichada": {"name": "Vichada", "capital": "Puerto Carreño", "lat": 5.0, "lng": -69.0, "code": "99"}
}

# Regions of Colombia (grouping of departments)
REGIONS = {
    "caribe": {
        "name": "Región Caribe",
        "departments": ["atlantico", "bolivar", "cesar", "cordoba", "guajira", "magdalena", "sucre", "san_andres"],
        "color": "#3498db"
    },
    "pacifico": {
        "name": "Región Pacífico", 
        "departments": ["choco", "valle_cauca", "cauca", "narino"],
        "color": "#2ecc71"
    },
    "andina": {
        "name": "Región Andina",
        "departments": ["antioquia", "boyaca", "caldas", "cundinamarca", "huila", "norte_santander", "quindio", "risaralda", "santander", "tolima", "bogota"],
        "color": "#e74c3c"
    },
    "orinoquia": {
        "name": "Región Orinoquía (Llanos Orientales)",
        "departments": ["arauca", "casanare", "meta", "vichada"],
        "color": "#f39c12"
    },
    "amazonia": {
        "name": "Región Amazonía",
        "departments": ["amazonas", "caqueta", "guainia", "guaviare", "putumayo", "vaupes"],
        "color": "#9b59b6"
    }
}

# Major municipalities (sample - would be expanded from official DANE data)
MAJOR_MUNICIPALITIES = {
    # Bogotá D.C.
    "bogota": {"name": "Bogotá D.C.", "department": "bogota", "lat": 4.6097, "lng": -74.0817, "population": 7181469},
    
    # Antioquia
    "medellin": {"name": "Medellín", "department": "antioquia", "lat": 6.2442, "lng": -75.5812, "population": 2533424},
    "bello": {"name": "Bello", "department": "antioquia", "lat": 6.3378, "lng": -75.5556, "population": 510737},
    "itagui": {"name": "Itagüí", "department": "antioquia", "lat": 6.1847, "lng": -75.5994, "population": 279894},
    "envigado": {"name": "Envigado", "department": "antioquia", "lat": 6.1717, "lng": -75.5900, "population": 232462},
    
    # Valle del Cauca  
    "cali": {"name": "Cali", "department": "valle_cauca", "lat": 3.4516, "lng": -76.5320, "population": 2227642},
    "buenaventura": {"name": "Buenaventura", "department": "valle_cauca", "lat": 3.8801, "lng": -77.0311, "population": 423927},
    "palmira": {"name": "Palmira", "department": "valle_cauca", "lat": 3.5399, "lng": -76.3036, "population": 308669},
    
    # Atlántico
    "barranquilla": {"name": "Barranquilla", "department": "atlantico", "lat": 10.9639, "lng": -74.7964, "population": 1274250},
    "soledad": {"name": "Soledad", "department": "atlantico", "lat": 10.9180, "lng": -74.7684, "population": 649692},
    
    # Bolívar
    "cartagena": {"name": "Cartagena de Indias", "department": "bolivar", "lat": 10.3910, "lng": -75.4794, "population": 1028736},
    
    # Santander
    "bucaramanga": {"name": "Bucaramanga", "department": "santander", "lat": 7.1254, "lng": -73.1198, "population": 528575},
    "floridablanca": {"name": "Floridablanca", "department": "santander", "lat": 7.0622, "lng": -73.0869, "population": 271728},
    
    # Norte de Santander
    "cucuta": {"name": "Cúcuta", "department": "norte_santander", "lat": 7.8939, "lng": -72.5078, "population": 777106},
    
    # Tolima
    "ibague": {"name": "Ibagué", "department": "tolima", "lat": 4.4389, "lng": -75.2322, "population": 569336},
    
    # Nariño
    "pasto": {"name": "Pasto", "department": "narino", "lat": 1.2136, "lng": -77.2811, "population": 464846},
    
    # Córdoba
    "monteria": {"name": "Montería", "department": "cordoba", "lat": 8.7575, "lng": -75.8906, "population": 460223},
    
    # Meta
    "villavicencio": {"name": "Villavicencio", "department": "meta", "lat": 4.1420, "lng": -73.6266, "population": 531275},
    
    # Cesar
    "valledupar": {"name": "Valledupar", "department": "cesar", "lat": 10.4631, "lng": -73.2532, "population": 493342},
    
    # Risaralda
    "pereira": {"name": "Pereira", "department": "risaralda", "lat": 4.8087, "lng": -75.6906, "population": 477027},
    
    # Caldas
    "manizales": {"name": "Manizales", "department": "caldas", "lat": 5.0703, "lng": -75.5138, "population": 400436},
    
    # Huila
    "neiva": {"name": "Neiva", "department": "huila", "lat": 2.9273, "lng": -75.2819, "population": 347501},
    
    # Cauca
    "popayan": {"name": "Popayán", "department": "cauca", "lat": 2.4419, "lng": -76.6061, "population": 318059},
    
    # Magdalena
    "santa_marta": {"name": "Santa Marta", "department": "magdalena", "lat": 11.2404, "lng": -74.2110, "population": 499716},
    
    # Boyacá
    "tunja": {"name": "Tunja", "department": "boyaca", "lat": 5.5353, "lng": -73.3678, "population": 191878},
    
    # Quindío
    "armenia": {"name": "Armenia", "department": "quindio", "lat": 4.5339, "lng": -75.6811, "population": 301224},
    
    # La Guajira
    "riohacha": {"name": "Riohacha", "department": "guajira", "lat": 11.5444, "lng": -72.9072, "population": 279516},
    
    # Chocó
    "quibdo": {"name": "Quibdó", "department": "choco", "lat": 5.6947, "lng": -76.6611, "population": 130825},
}


def get_department_by_code(code: str) -> dict:
    """Get department info by DANE code."""
    for key, dept in DEPARTMENTS.items():
        if dept["code"] == code:
            return {
                "code": dept["code"],
                "name": dept["name"],
                "capital": dept["capital"],
                "lat": dept["lat"],
                "lon": dept.get("lng", dept.get("lon", 0)),
                "key": key
            }
    return None


def get_departments_list() -> list:
    """Get list of all departments with standardized format."""
    result = []
    for key, dept in DEPARTMENTS.items():
        result.append({
            "code": dept["code"],
            "name": dept["name"],
            "capital": dept["capital"],
            "lat": dept["lat"],
            "lon": dept.get("lng", dept.get("lon", 0))
        })
    # Sort by name
    return sorted(result, key=lambda x: x["name"])


def get_department_center(code: str) -> dict:
    """Get center coordinates for a department."""
    dept = get_department_by_code(code)
    if dept:
        return {"lat": dept["lat"], "lon": dept["lon"]}
    return None


def get_department_bounds(code: str) -> dict:
    """Get approximate bounds for a department (simplified)."""
    dept = get_department_by_code(code)
    if dept:
        # Approximate 1-degree bounds around center
        return {
            "north": dept["lat"] + 1.0,
            "south": dept["lat"] - 1.0,
            "east": dept["lon"] + 1.0,
            "west": dept["lon"] - 1.0
        }
    return None


def get_municipalities_by_department(department_key: str) -> list:
    """Get all municipalities in a department."""
    return [
        {**muni, "key": key}
        for key, muni in MAJOR_MUNICIPALITIES.items()
        if muni["department"] == department_key
    ]


def get_departments_by_region(region_key: str) -> list:
    """Get all departments in a region."""
    if region_key not in REGIONS:
        return []
    return [
        {**DEPARTMENTS[dept_key], "key": dept_key}
        for dept_key in REGIONS[region_key]["departments"]
        if dept_key in DEPARTMENTS
    ]
