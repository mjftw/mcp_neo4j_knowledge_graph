import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl, CreateEntityRequest
from src.tools.create_relations import create_relations_impl, CreateRelationRequest
from src.tools.introspect_schema import (
    introspect_schema_impl,
    SchemaIntrospectionResult
)


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


async def create_test_data(driver: AsyncDriver) -> Dict[str, List[Dict]]:
    """Create test entities and relations for schema testing"""
    # Create entities of different types
    entities = [
        CreateEntityRequest(
            type="Person",
            properties={
                "name": f"person_{uuid.uuid4()}",
                "age": 30,
                "id": f"person_{uuid.uuid4()}"
            }
        ),
        CreateEntityRequest(
            type="Company",
            properties={
                "name": f"company_{uuid.uuid4()}",
                "founded": 2020,
                "id": f"company_{uuid.uuid4()}"
            }
        ),
        CreateEntityRequest(
            type="Product",
            properties={
                "name": f"product_{uuid.uuid4()}",
                "price": 99.99,
                "id": f"product_{uuid.uuid4()}"
            }
        )
    ]
    
    entity_result = await create_entities_impl(driver, entities)
    created_entities = entity_result.result
    
    # Create relations between entities
    relations = [
        CreateRelationRequest(
            type="WORKS_AT",
            from_id=created_entities[0].id,  # Person
            to_id=created_entities[1].id     # Company
        ),
        CreateRelationRequest(
            type="PRODUCES",
            from_id=created_entities[1].id,  # Company
            to_id=created_entities[2].id     # Product
        )
    ]
    
    relation_result = await create_relations_impl(driver, relations)
    
    return {
        "entities": [e.__dict__ for e in created_entities],
        "relations": [r.__dict__ for r in relation_result.result]
    }


@pytest.mark.asyncio
async def test_introspect_empty_database(driver: AsyncDriver):
    """Test introspecting schema of an empty database"""
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    assert isinstance(result, SchemaIntrospectionResult)
    assert isinstance(result.node_labels, list)
    assert isinstance(result.relationship_types, list)
    assert isinstance(result.node_properties, dict)
    assert isinstance(result.relationship_properties, dict)


@pytest.mark.asyncio
async def test_introspect_with_data(driver: AsyncDriver):
    """Test introspecting schema after creating test data"""
    # Arrange
    await create_test_data(driver)
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    assert isinstance(result, SchemaIntrospectionResult)
    
    # Check node labels
    assert "Person" in result.node_labels
    assert "Company" in result.node_labels
    assert "Product" in result.node_labels
    
    # Check relationship types
    assert "WORKS_AT" in result.relationship_types
    assert "PRODUCES" in result.relationship_types
    
    # Check node properties
    assert "name" in result.node_properties.get("Person", [])
    assert "age" in result.node_properties.get("Person", [])
    assert "founded" in result.node_properties.get("Company", [])
    assert "price" in result.node_properties.get("Product", [])


@pytest.mark.asyncio
async def test_introspect_property_types(driver: AsyncDriver):
    """Test introspecting schema with different property types"""
    # Arrange
    entity = CreateEntityRequest(
        type="TestEntity",
        properties={
            "name": f"test_{uuid.uuid4()}",
            "string_prop": "text",
            "int_prop": 42,
            "float_prop": 3.14,
            "bool_prop": True,
            "null_prop": None,
            "id": f"test_{uuid.uuid4()}"
        }
    )
    await create_entities_impl(driver, [entity])
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    assert isinstance(result, SchemaIntrospectionResult)
    test_entity_props = result.node_properties.get("TestEntity", [])
    
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
    entities = [
        CreateEntityRequest(
            type="TestEntity",
            properties={
                "name": f"test_{uuid.uuid4()}",
                "id": f"test_{uuid.uuid4()}"
            }
        ) for _ in range(2)
    ]
    result = await create_entities_impl(driver, entities)
    created_entities = result.result
    
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
        await session.run(query, {
            "from_id": created_entities[0].id,
            "to_id": created_entities[1].id
        })
    
    # Act
    result = await introspect_schema_impl(driver)
    
    # Assert
    assert isinstance(result, SchemaIntrospectionResult)
    rel_props = result.relationship_properties.get("HAS_RELATION", [])
    
    assert "since" in rel_props
    assert "weight" in rel_props
    assert "active" in rel_props 