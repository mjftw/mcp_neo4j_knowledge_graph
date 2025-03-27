import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl
from src.tools.create_relations import create_relations_impl


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


async def create_test_entities(
    driver: AsyncDriver, 
    count: int = 2, 
    type_prefix: str = "TestType"
) -> List[Dict]:
    """Helper to create test entities for relation testing"""
    entities = [
        {
            "type": f"{type_prefix}{i}",
            "properties": {
                "name": f"test_entity_{uuid.uuid4()}"
            }
        }
        for i in range(count)
    ]
    
    result = await create_entities_impl(driver, entities)
    return [node for node in result["result"]]


@pytest.mark.asyncio
async def test_should_create_single_relation(driver: AsyncDriver):
    """When creating a relation between two entities, should create it with correct type"""
    # Arrange
    nodes = await create_test_entities(driver, 2)
    relation = {
        "from": nodes[0]["id"],
        "to": nodes[1]["id"],
        "type": "TEST_RELATION"
    }
    
    # Act
    result = await create_relations_impl(driver, [relation])
    
    # Assert
    assert "result" in result
    assert len(result["result"]) == 1
    created_rel = result["result"][0]
    assert created_rel["type"] == "TEST_RELATION"
    assert created_rel["from"] == nodes[0]["id"]
    assert created_rel["to"] == nodes[1]["id"]


@pytest.mark.asyncio
async def test_should_create_multiple_relations(driver: AsyncDriver):
    """When creating multiple relations, should create all with correct types and directions"""
    # Arrange
    nodes = await create_test_entities(driver, 3)
    relations = [
        {
            "from": nodes[0]["id"],
            "to": nodes[1]["id"],
            "type": "RELATION_1"
        },
        {
            "from": nodes[1]["id"],
            "to": nodes[2]["id"],
            "type": "RELATION_2"
        }
    ]
    
    # Act
    result = await create_relations_impl(driver, relations)
    
    # Assert
    assert len(result["result"]) == 2
    for i, created_rel in enumerate(result["result"]):
        assert created_rel["type"] == relations[i]["type"]
        assert created_rel["from"] == relations[i]["from"]
        assert created_rel["to"] == relations[i]["to"]


@pytest.mark.asyncio
async def test_should_create_bidirectional_relations(driver: AsyncDriver):
    """When creating relations in both directions, should create both relations correctly"""
    # Arrange
    nodes = await create_test_entities(driver, 2)
    relations = [
        {
            "from": nodes[0]["id"],
            "to": nodes[1]["id"],
            "type": "RELATES_TO"
        },
        {
            "from": nodes[1]["id"],
            "to": nodes[0]["id"],
            "type": "RELATES_TO"
        }
    ]
    
    # Act
    result = await create_relations_impl(driver, relations)
    
    # Assert
    assert len(result["result"]) == 2
    assert result["result"][0]["from"] == nodes[0]["id"]
    assert result["result"][0]["to"] == nodes[1]["id"]
    assert result["result"][1]["from"] == nodes[1]["id"]
    assert result["result"][1]["to"] == nodes[0]["id"]


@pytest.mark.asyncio
async def test_should_handle_nonexistent_entity_gracefully(driver: AsyncDriver):
    """When creating relation with nonexistent entity, should return empty result"""
    # Arrange
    nodes = await create_test_entities(driver, 1)
    relation = {
        "from": nodes[0]["id"],
        "to": "nonexistent_entity",
        "type": "TEST_RELATION"
    }
    
    # Act
    result = await create_relations_impl(driver, [relation])
    
    # Assert
    assert "result" in result
    assert len(result["result"]) == 0  # No relations should be created


@pytest.mark.asyncio
async def test_should_create_self_relation(driver: AsyncDriver):
    """When creating relation from entity to itself, should create self-referential relation"""
    # Arrange
    nodes = await create_test_entities(driver, 1)
    relation = {
        "from": nodes[0]["id"],
        "to": nodes[0]["id"],
        "type": "SELF_RELATES"
    }
    
    # Act
    result = await create_relations_impl(driver, [relation])
    
    # Assert
    assert len(result["result"]) == 1
    created_rel = result["result"][0]
    assert created_rel["from"] == nodes[0]["id"]
    assert created_rel["to"] == nodes[0]["id"]
    assert created_rel["type"] == "SELF_RELATES"


@pytest.mark.asyncio
async def test_should_persist_relation_in_database(driver: AsyncDriver):
    """When creating a relation, should be able to retrieve it from the database"""
    # Arrange
    nodes = await create_test_entities(driver, 2)
    relation = {
        "from": nodes[0]["id"],
        "to": nodes[1]["id"],
        "type": "TEST_RELATION"
    }
    
    # Act
    await create_relations_impl(driver, [relation])
    
    # Assert - Verify we can retrieve the relation
    async with driver.session() as session:
        query = """
        MATCH (a:Entity {id: $from_id})-[r:TEST_RELATION]->(b:Entity {id: $to_id})
        RETURN r
        """
        result = await session.run(
            query,
            {
                "from_id": nodes[0]["id"],
                "to_id": nodes[1]["id"]
            }
        )
        record = await result.single()
        
        assert record is not None
        assert record["r"].type == "TEST_RELATION" 