import uuid
from typing import AsyncGenerator

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl


@pytest.fixture
async def driver() -> AsyncGenerator[AsyncDriver, None]:
    # Using test database configuration
    driver = AsyncGraphDatabase.driver(
        "neo4j://localhost:7687",
        auth=("neo4j", "password")
    )
    
    try:
        await driver.verify_connectivity()
        yield driver
    finally:
        await driver.close()


def create_test_entity(name_prefix: str = "test") -> dict:
    """Create a test entity with a unique ID to avoid conflicts"""
    unique_id = str(uuid.uuid4())
    return {
        "type": "TestEntity",
        "properties": {
            "name": f"{name_prefix}_{unique_id}"
        }
    }


@pytest.mark.asyncio
async def test_should_create_single_entity(driver: AsyncDriver):
    """When creating a single entity, should create it with all properties"""
    # Arrange
    entity = create_test_entity()

    # Act
    result = await create_entities_impl(driver, [entity])

    # Assert
    assert "result" in result
    assert len(result["result"]) == 1
    created_node = result["result"][0]
    assert created_node["id"] == entity["properties"]["name"]
    assert created_node["type"] == entity["type"]
    assert created_node["name"] == entity["properties"]["name"]


@pytest.mark.asyncio
async def test_should_create_multiple_entities(driver: AsyncDriver):
    """When creating multiple entities, should create all with their respective properties"""
    # Arrange
    entities = [
        create_test_entity("test1"),
        create_test_entity("test2"),
        create_test_entity("test3")
    ]

    # Act
    result = await create_entities_impl(driver, entities)

    # Assert
    assert "result" in result
    assert len(result["result"]) == 3
    
    # Verify each entity was created correctly
    for i, created_node in enumerate(result["result"]):
        assert created_node["id"] == entities[i]["properties"]["name"]
        assert created_node["type"] == entities[i]["type"]
        assert created_node["name"] == entities[i]["properties"]["name"]


@pytest.mark.asyncio
async def test_should_create_entity_with_custom_type(driver: AsyncDriver):
    """When creating an entity with custom type, should preserve the type"""
    # Arrange
    entity = create_test_entity()
    entity["type"] = "CustomType"
    
    # Act
    result = await create_entities_impl(driver, [entity])
    
    # Assert
    assert "result" in result
    created_node = result["result"][0]
    assert created_node["type"] == "CustomType"


@pytest.mark.asyncio
async def test_should_handle_duplicate_entity_creation(driver: AsyncDriver):
    """When creating the same entity twice, should handle it idempotently"""
    # Arrange
    entity = create_test_entity()
    
    # Act - Create the same entity twice
    result1 = await create_entities_impl(driver, [entity])
    result2 = await create_entities_impl(driver, [entity])
    
    # Assert - Both operations should succeed and return the same data
    assert len(result1["result"]) == 1
    assert len(result2["result"]) == 1
    
    node1 = result1["result"][0]
    node2 = result2["result"][0]
    
    # The nodes should have the same properties
    assert node1["id"] == node2["id"]
    assert node1["type"] == node2["type"]
    assert node1["name"] == node2["name"]


@pytest.mark.asyncio
async def test_should_persist_entity_in_database(driver: AsyncDriver):
    """When creating an entity, should be able to retrieve it from the database"""
    # Arrange
    entity = create_test_entity()
    
    # Act
    await create_entities_impl(driver, [entity])
    
    # Assert - Verify we can retrieve the entity
    async with driver.session() as session:
        query = """
        MATCH (n:Entity {id: $id})
        RETURN n
        """
        result = await session.run(query, {"id": entity["properties"]["name"]})
        record = await result.single()
        
        assert record is not None
        node = record["n"]
        assert node["id"] == entity["properties"]["name"]
        assert node["type"] == entity["type"]
        assert node["name"] == entity["properties"]["name"]


@pytest.mark.asyncio
async def test_should_handle_empty_properties(driver: AsyncDriver):
    """When creating an entity with empty properties, should handle it gracefully"""
    # Arrange
    entity = {
        "type": "TestEntity",
        "properties": {}
    }
    
    # Act
    result = await create_entities_impl(driver, [entity])
    
    # Assert
    assert "result" in result
    assert len(result["result"]) == 1
    created_node = result["result"][0]
    assert created_node["type"] == "TestEntity"
    # ID and name should be None since properties were empty
    assert created_node["id"] is None
    assert created_node["name"] is None 