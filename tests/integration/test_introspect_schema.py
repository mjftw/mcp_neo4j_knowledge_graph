import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl
from src.tools.create_relations import create_relations_impl
from src.tools.introspect_schema import introspect_schema_impl


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


async def create_test_data(driver: AsyncDriver) -> Dict[str, List[Dict]]:
    """Create test entities and relations for schema testing"""
    # Create entities of different types
    entities = [
        {
            "type": "Person",
            "properties": {
                "name": f"person_{uuid.uuid4()}",
                "age": 30
            }
        },
        {
            "type": "Company",
            "properties": {
                "name": f"company_{uuid.uuid4()}",
                "founded": 2020
            }
        },
        {
            "type": "Product",
            "properties": {
                "name": f"product_{uuid.uuid4()}",
                "price": 99.99
            }
        }
    ]
    
    entity_result = await create_entities_impl(driver, entities)
    created_entities = entity_result["result"]
    
    # Create relations between entities
    relations = [
        {
            "from": created_entities[0]["id"],  # Person
            "to": created_entities[1]["id"],    # Company
            "type": "WORKS_AT"
        },
        {
            "from": created_entities[1]["id"],  # Company
            "to": created_entities[2]["id"],    # Product
            "type": "PRODUCES"
        }
    ]
    
    relation_result = await create_relations_impl(driver, relations)
    
    return {
        "entities": created_entities,
        "relations": relation_result["result"]
    }


@pytest.mark.asyncio
async def test_introspect_empty_database(driver: AsyncDriver):
    """Test introspecting schema of an empty database"""
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    assert "schema" in result
    schema = result["schema"]
    assert "node_labels" in schema
    assert "relationship_types" in schema
    assert "node_properties" in schema
    assert "relationship_properties" in schema


@pytest.mark.asyncio
async def test_introspect_with_data(driver: AsyncDriver):
    """Test introspecting schema after creating test data"""
    # Arrange
    await create_test_data(driver)
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    schema = result["schema"]
    
    # Check node labels
    assert "Entity" in schema["node_labels"]
    assert "Person" in schema["node_labels"]
    assert "Company" in schema["node_labels"]
    assert "Product" in schema["node_labels"]
    
    # Check relationship types
    assert "WORKS_AT" in schema["relationship_types"]
    assert "PRODUCES" in schema["relationship_types"]
    
    # Check node properties
    assert "name" in schema["node_properties"].get("Person", [])
    assert "age" in schema["node_properties"].get("Person", [])
    assert "founded" in schema["node_properties"].get("Company", [])
    assert "price" in schema["node_properties"].get("Product", [])


@pytest.mark.asyncio
async def test_introspect_property_types(driver: AsyncDriver):
    """Test introspecting schema with different property types"""
    # Arrange
    entity = {
        "type": "TestEntity",
        "properties": {
            "name": f"test_{uuid.uuid4()}",
            "string_prop": "text",
            "int_prop": 42,
            "float_prop": 3.14,
            "bool_prop": True,
            "null_prop": None
        }
    }
    await create_entities_impl(driver, [entity])
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    schema = result["schema"]
    test_entity_props = schema["node_properties"].get("TestEntity", [])
    
    assert "string_prop" in test_entity_props
    assert "int_prop" in test_entity_props
    assert "float_prop" in test_entity_props
    assert "bool_prop" in test_entity_props
    # Note: null_prop is not expected to be present since Neo4j doesn't store null properties


@pytest.mark.asyncio
async def test_introspect_relationship_properties(driver: AsyncDriver):
    """Test introspecting schema for relationships with properties"""
    # Arrange
    # First create two entities
    entities = await create_test_entities(driver, 2)
    
    # Create a relationship with properties using Cypher
    async with driver.session() as session:
        query = """
        MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id})
        CREATE (a)-[r:HAS_RELATION {
            since: 2024,
            weight: 0.5,
            active: true
        }]->(b)
        """
        await session.run(query, {"from_id": entities[0]["id"], "to_id": entities[1]["id"]})
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    schema = result["schema"]
    rel_props = schema["relationship_properties"].get("HAS_RELATION", [])
    
    assert "since" in rel_props
    assert "weight" in rel_props
    assert "active" in rel_props


async def create_test_entities(
    driver: AsyncDriver, 
    count: int = 2, 
    type_prefix: str = "TestType"
) -> List[Dict]:
    """Helper to create test entities"""
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