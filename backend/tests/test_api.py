"""
Tests for API endpoints.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_organizations_empty(client: AsyncClient):
    """Test listing organizations when database is empty."""
    response = await client.get("/api/organizations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_create_organization(client: AsyncClient):
    """Test creating a new organization."""
    organization_data = {
        "name": "Test Organization",
        "url": "https://example.com",
        "description": "A test organization",
        "latitude": 40.0,
        "longitude": -3.0
    }
    
    response = await client.post("/api/organizations", json=organization_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Organization"
    assert data["url"] == "https://example.com"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_get_organization(client: AsyncClient):
    """Test getting a specific organization."""
    # First create an organization
    organization_data = {
        "name": "Get Test Organization",
        "url": "https://example.com"
    }
    create_response = await client.post("/api/organizations", json=organization_data)
    created = create_response.json()
    
    # Then get it
    response = await client.get(f"/api/organizations/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get Test Organization"


@pytest.mark.asyncio
async def test_get_organization_not_found(client: AsyncClient):
    """Test getting a non-existent organization."""
    response = await client.get("/api/organizations/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_variable_keys(client: AsyncClient):
    """Test getting unique variable keys."""
    response = await client.get("/api/variables/keys")
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert isinstance(data["keys"], list)


@pytest.mark.asyncio
async def test_venn_available_keys(client: AsyncClient):
    """Test getting available keys for Venn diagram."""
    response = await client.get("/api/venn/available-keys")
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data


@pytest.mark.asyncio
async def test_venn_data_no_vars(client: AsyncClient):
    """Test Venn data endpoint without variables."""
    response = await client.get("/api/venn/data?vars=")
    assert response.status_code == 200
    data = response.json()
    assert "sets" in data
    assert "intersections" in data


@pytest.mark.asyncio
async def test_map_organizations(client: AsyncClient):
    """Test getting organizations for map."""
    response = await client.get("/api/map/organizations")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data


@pytest.mark.asyncio
async def test_map_locations(client: AsyncClient):
    """Test getting locations for map."""
    response = await client.get("/api/map/locations")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
