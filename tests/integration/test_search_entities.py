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
async def test_should_find_entity_by_exact_name_match(driver: AsyncDriver):
    """When searching with exact name match, should return only the matching entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
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
async def test_should_find_multiple_entities_with_fuzzy_name_match(driver: AsyncDriver):
    """When searching with fuzzy name match, should return all partially matching entities"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
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
async def test_should_filter_entities_by_type(driver: AsyncDriver):
    """When filtering by entity type, should return only entities of that type"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=test_id,
        entity_type="Person",
        fuzzy_match=True
    )
    
    # Assert
    assert len(result["results"]) == 2
    for node in result["results"]:
        assert "Person" in node["type"]


@pytest.mark.asyncio
async def test_should_find_entity_by_property_value(driver: AsyncDriver):
    """When searching by specific property value, should return matching entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
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
async def test_should_include_relationships_when_requested(driver: AsyncDriver):
    """When relationships are included, should return entity with its relationships"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
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
    
    relationships = node["relationships"]
    rel_types = [rel["type"] for rel in relationships]
    assert "WORKS_AT" in rel_types
    assert "MANAGES" in rel_types


@pytest.mark.asyncio
async def test_should_return_empty_results_for_nonexistent_entity(driver: AsyncDriver):
    """When searching for nonexistent entity, should return empty results"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"NonexistentPerson_{test_id}"
    )
    
    # Assert
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_should_match_case_insensitively(driver: AsyncDriver):
    """When searching with different case, should match case-insensitively"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
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
async def test_should_find_entity_by_exact_name(driver: AsyncDriver):
    """When searching for entity by exact name, should return matching entity with properties"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)

    # Act
    result = await search_entities_impl(
        driver,
        search_term=f"Tech Corp_{test_id}",
        properties=["name"],
        fuzzy_match=False
    )

    # Assert
    assert len(result["results"]) == 1, f"Expected 1 result, got {len(result['results'])}"
    node = result["results"][0]
    assert node["properties"]["name"] == f"Tech Corp_{test_id}"
    assert node["properties"]["industry"] == "Technology"


@pytest.mark.asyncio
async def test_should_find_entity_by_type_and_property(driver: AsyncDriver):
    """When searching with type and property filters, should return only matching entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)

    # Act
    results = await search_entities_impl(
        driver,
        search_term=test_id,
        entity_type="Company",
        properties=["name"],
        fuzzy_match=True
    )

    # Assert
    assert len(results["results"]) == 1, f"Expected 1 result, got {len(results['results'])}"
    assert results["results"][0]["properties"]["name"] == f"Tech Corp_{test_id}"
    assert results["results"][0]["properties"]["industry"] == "Technology" 