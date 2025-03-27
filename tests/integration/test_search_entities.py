import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl
from src.tools.create_relations import create_relations_impl
from src.tools.search_entities import search_entities_impl


@pytest.fixture
async def driver() -> AsyncGenerator[AsyncDriver, None]:
    driver = AsyncGraphDatabase.driver(
        "neo4j://localhost:7687",
        auth=("neo4j", "password")
    )
    
    try:
        await driver.verify_connectivity()
        yield driver
    finally:
        await driver.close()


async def create_test_dataset(driver: AsyncDriver, test_id: str) -> Dict[str, List[Dict]]:
    """Create a test dataset with various entities and relationships
    
    Args:
        driver: Neo4j async driver instance
        test_id: Unique identifier for this test to ensure data isolation
    """
    # Create entities
    entities = [
        {
            "type": "Person",
            "properties": {
                "name": f"John Smith_{test_id}",
                "age": 30,
                "email": f"john_{test_id}@example.com"
            }
        },
        {
            "type": "Person",
            "properties": {
                "name": f"Jane Smith_{test_id}",
                "age": 28,
                "email": f"jane_{test_id}@example.com"
            }
        },
        {
            "type": "Company",
            "properties": {
                "name": f"Tech Corp_{test_id}",
                "industry": "Technology"
            }
        },
        {
            "type": "Project",
            "properties": {
                "name": f"Project Alpha_{test_id}",
                "status": "Active"
            }
        }
    ]
    
    entity_result = await create_entities_impl(driver, entities)
    created_entities = entity_result["result"]
    
    # Create relationships
    relations = [
        {
            "from": created_entities[0]["id"],  # John
            "to": created_entities[2]["id"],    # Tech Corp
            "type": "WORKS_AT"
        },
        {
            "from": created_entities[1]["id"],  # Jane
            "to": created_entities[2]["id"],    # Tech Corp
            "type": "WORKS_AT"
        },
        {
            "from": created_entities[0]["id"],  # John
            "to": created_entities[3]["id"],    # Project Alpha
            "type": "MANAGES"
        }
    ]
    
    relation_result = await create_relations_impl(driver, relations)
    
    return {
        "entities": created_entities,
        "relations": relation_result["result"]
    }


@pytest.mark.asyncio
async def test_search_by_exact_name(driver: AsyncDriver):
    """Test searching entities by exact name match"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"John Smith_{test_id}",
        fuzzy_match=False
    )
    
    # Assert
    assert len(result["results"]) == 1
    assert result["results"][0]["properties"]["name"] == f"John Smith_{test_id}"


@pytest.mark.asyncio
async def test_search_by_fuzzy_name(driver: AsyncDriver):
    """Test searching entities with fuzzy name matching"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"Smith_{test_id}",
        fuzzy_match=True
    )
    
    # Assert
    assert len(result["results"]) == 2  # Should find both John and Jane Smith
    names = [node["properties"]["name"] for node in result["results"]]
    assert f"John Smith_{test_id}" in names
    assert f"Jane Smith_{test_id}" in names


@pytest.mark.asyncio
async def test_search_by_entity_type(driver: AsyncDriver):
    """Test searching entities by type"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=test_id,  # Use test_id to find only our test data
        entity_type="Person",
        fuzzy_match=True
    )
    
    # Assert
    assert len(result["results"]) == 2
    for node in result["results"]:
        assert "Person" in node["type"]  # type is now an array of labels


@pytest.mark.asyncio
async def test_search_with_property_filter(driver: AsyncDriver):
    """Test searching entities with specific property filter"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"john_{test_id}@example.com",
        properties=["email"]
    )
    
    # Assert
    assert len(result["results"]) == 1
    assert result["results"][0]["properties"]["email"] == f"john_{test_id}@example.com"


@pytest.mark.asyncio
async def test_search_with_relationships(driver: AsyncDriver):
    """Test searching entities and including their relationships"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"John Smith_{test_id}",
        include_relationships=True
    )
    
    # Assert
    assert len(result["results"]) == 1
    node = result["results"][0]
    assert "relationships" in node
    
    # Should have two relationships: WORKS_AT and MANAGES
    relationships = node["relationships"]
    rel_types = [rel["type"] for rel in relationships]
    assert "WORKS_AT" in rel_types
    assert "MANAGES" in rel_types


@pytest.mark.asyncio
async def test_search_no_results(driver: AsyncDriver):
    """Test searching with a term that should return no results"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"NonexistentPerson_{test_id}"
    )
    
    # Assert
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_search_case_insensitive(driver: AsyncDriver):
    """Test case-insensitive search"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"john smith_{test_id}",  # lowercase
        fuzzy_match=True
    )
    
    # Assert
    assert len(result["results"]) == 1
    assert result["results"][0]["properties"]["name"] == f"John Smith_{test_id}"


@pytest.mark.asyncio
async def test_search_multiple_properties(driver: AsyncDriver):
    """Test searching across multiple specified properties"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)

    # Search by name with test_id to ensure we only get our test data
    result = await search_entities_impl(
        driver,
        search_term=f"Tech Corp_{test_id}",  # Search for exact entity name
        properties=["name"],
        fuzzy_match=False  # Use exact match for first search
    )

    assert len(result["results"]) == 1, f"Expected 1 result, got {len(result['results'])}"
    node = result["results"][0]
    assert node["properties"]["name"] == f"Tech Corp_{test_id}"
    assert node["properties"]["industry"] == "Technology"

    # Search by name and industry with test_id to ensure we only get our test data
    results = await search_entities_impl(
        driver,
        search_term=test_id,  # Search for test_id to get our specific entity
        entity_type="Company",
        properties=["name"],  # Just search in name to find our test entity
        fuzzy_match=True
    )

    assert len(results["results"]) == 1, f"Expected 1 result, got {len(results['results'])}"
    assert results["results"][0]["properties"]["name"] == f"Tech Corp_{test_id}"
    assert results["results"][0]["properties"]["industry"] == "Technology" 