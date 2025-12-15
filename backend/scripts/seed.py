"""
Seed script - Creates example organizations with sample data
Focused on women-led civil society organizations for peace-building in Colombia
"""
import asyncio
import random
from datetime import datetime
from sqlalchemy import select

# Add parent directory to path
import sys
sys.path.insert(0, '/app')

from app.db.base import async_session_maker, init_db
from app.models.db_models import Organization, Variable, Location, TerritorialScope, OrganizationApproach


# Sample data for organizations - Women-led peace-building organizations in Colombia
ORGANIZATIONS_DATA = [
    {
        "name": "Mujeres Sororas y Defensoras",
        "description": "Organización de mujeres defensoras de derechos humanos en el sur de Colombia",
        "latitude": 1.2136,
        "longitude": -77.2811,
        "territorial_scope": TerritorialScope.MUNICIPAL,
        "department_code": "52",
        "approach": OrganizationApproach.BOTTOM_UP,
        "leader_is_woman": True,
    },
    {
        "name": "Casa conexión la Karacola",
        "description": "Espacio de encuentro y formación para mujeres constructoras de paz",
        "latitude": 4.6097,
        "longitude": -74.0817,
        "territorial_scope": TerritorialScope.REGIONAL,
        "department_code": "11",
        "approach": OrganizationApproach.BOTTOM_UP,
        "leader_is_woman": True,
    },
    {
        "name": "Asociación de Mujeres Buscando Libertad (Asmubuli)",
        "description": "Organización de mujeres víctimas del conflicto armado en Buenaventura",
        "latitude": 3.8801,
        "longitude": -77.0311,
        "territorial_scope": TerritorialScope.MUNICIPAL,
        "department_code": "76",
        "approach": OrganizationApproach.BOTTOM_UP,
        "leader_is_woman": True,
    },
    {
        "name": "Andariegas",
        "description": "Colectivo de mujeres que promueven la memoria histórica y la paz",
        "latitude": 6.2442,
        "longitude": -75.5812,
        "territorial_scope": TerritorialScope.REGIONAL,
        "department_code": "05",
        "approach": OrganizationApproach.BOTTOM_UP,
        "leader_is_woman": True,
    },
]


async def seed_database():
    """
    Seeds the database with example organizations and related data.
    """
    print("🌱 Starting database seeding...")
    
    # Initialize database tables
    await init_db()
    
    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(Organization))
        existing = result.scalars().all()
        
        if existing:
            print(f"⚠️  Database already has {len(existing)} organizations. Skipping seed.")
            return
        
        # Create organizations
        for i, data in enumerate(ORGANIZATIONS_DATA, 1):
            print(f"  Creating organization {i}/{len(ORGANIZATIONS_DATA)}: {data['name']}")
            
            # Create organization with Colombian peace-building fields
            organization = Organization(
                name=data["name"],
                url=data.get("url"),
                description=data.get("description"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                territorial_scope=data.get("territorial_scope", TerritorialScope.MUNICIPAL),
                department_code=data.get("department_code"),
                approach=data.get("approach", OrganizationApproach.UNKNOWN),
                leader_is_woman=data.get("leader_is_woman", True),
                is_peace_building=True,
                women_count=random.randint(10, 200)
            )
            session.add(organization)
            await session.flush()  # Get the ID
            
            # Create location
            if data.get("latitude") and data.get("longitude"):
                location = Location(
                    organization_id=organization.id,
                    name=f"Sede de {data['name']}",
                    geojson={
                        "type": "Point",
                        "coordinates": [data["longitude"], data["latitude"]]
                    },
                    properties={
                        "department_code": data.get("department_code"),
                    }
                )
                session.add(location)
        
        # Commit all changes
        await session.commit()
        print(f"✅ Successfully seeded {len(ORGANIZATIONS_DATA)} organizations!")


async def clear_database():
    """
    Clears all data from the database.
    """
    print("🗑️  Clearing database...")
    
    async with async_session_maker() as session:
        await session.execute("TRUNCATE TABLE locations, variables, scrape_logs, organizations RESTART IDENTITY CASCADE")
        await session.commit()
    
    print("✅ Database cleared!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        asyncio.run(clear_database())
    else:
        asyncio.run(seed_database())
