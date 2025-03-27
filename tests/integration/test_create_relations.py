import uuid
from typing import AsyncGenerator, List, Tuple

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl, CreateEntityRequest
from src.tools.create_relations import (
    create_relations_impl,
    CreateRelationRequest,
    Relation,
    CreateRelationsResult
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


async def create_test_entities(driver: AsyncDriver, count: int = 2) -> List[str]:
    """Create test entities and return their IDs"""
    entities = []
    for i in range(count):
        unique_id = str(uuid.uuid4())
        entities.append(CreateEntityRequest(
            type="TestEntity",
            properties={
                "name": f"test_{unique_id}",
                "id": f"test_{unique_id}"  # Explicitly set ID
            }
        ))
    
    result = await create_entities_impl(driver, entities)
    return [entity.id for entity in result.result]


@pytest.mark.asyncio
async def test_should_create_single_relation(driver: AsyncDriver):
    """When creating a single relation, should create it between the specified entities"""
    # Arrange
    [from_id, to_id] = await create_test_entities(driver, 2)
    relation = CreateRelationRequest(
        type="TEST_RELATION",
        from_id=from_id,
        to_id=to_id
    )

    # Act
    result = await create_relations_impl(driver, [relation])

    # Assert
    assert isinstance(result, CreateRelationsResult)
    assert len(result.result) == 1
    created_relation = result.result[0]
    assert isinstance(created_relation, Relation)
    assert created_relation.type == "TEST_RELATION"
    assert created_relation.from_id == from_id
    assert created_relation.to_id == to_id


@pytest.mark.asyncio
async def test_should_create_multiple_relations(driver: AsyncDriver):
    """When creating multiple relations, should create all with their respective types"""
    # Arrange
    entity_ids = await create_test_entities(driver, 3)
    relations = [
        CreateRelationRequest(
            type="RELATION_1",
            from_id=entity_ids[0],
            to_id=entity_ids[1]
        ),
        CreateRelationRequest(
            type="RELATION_2",
            from_id=entity_ids[1],
            to_id=entity_ids[2]
        )
    ]

    # Act
    result = await create_relations_impl(driver, relations)

    # Assert
    assert isinstance(result, CreateRelationsResult)
    assert len(result.result) == 2
    
    # Verify each relation was created correctly
    for i, created_relation in enumerate(result.result):
        assert isinstance(created_relation, Relation)
        assert created_relation.type == relations[i].type
        assert created_relation.from_id == relations[i].from_id
        assert created_relation.to_id == relations[i].to_id


@pytest.mark.asyncio
async def test_should_handle_duplicate_relation_creation(driver: AsyncDriver):
    """When creating the same relation twice, should handle it gracefully"""
    # Arrange
    [from_id, to_id] = await create_test_entities(driver, 2)
    relation = CreateRelationRequest(
        type="TEST_RELATION",
        from_id=from_id,
        to_id=to_id
    )
    
    # Act - Create the same relation twice
    result1 = await create_relations_impl(driver, [relation])
    result2 = await create_relations_impl(driver, [relation])
    
    # Assert - Both operations should succeed
    assert isinstance(result1, CreateRelationsResult)
    assert isinstance(result2, CreateRelationsResult)
    assert len(result1.result) == 1
    assert len(result2.result) == 1
    
    rel1 = result1.result[0]
    rel2 = result2.result[0]
    assert isinstance(rel1, Relation)
    assert isinstance(rel2, Relation)
    
    # The relations should have the same properties
    assert rel1.type == rel2.type
    assert rel1.from_id == rel2.from_id
    assert rel1.to_id == rel2.to_id


@pytest.mark.asyncio
async def test_should_persist_relation_in_database(driver: AsyncDriver):
    """When creating a relation, should be able to retrieve it from the database"""
    # Arrange
    [from_id, to_id] = await create_test_entities(driver, 2)
    relation = CreateRelationRequest(
        type="TEST_RELATION",
        from_id=from_id,
        to_id=to_id
    )
    
    # Act
    result = await create_relations_impl(driver, [relation])
    created_relation = result.result[0]
    
    # Assert - Verify we can retrieve the relation
    async with driver.session() as session:
        query = """
        MATCH (a:Entity {id: $from_id})-[r]->(b:Entity {id: $to_id})
        RETURN type(r) as type, a.id as from_id, b.id as to_id
        """
        result = await session.run(query, {
            "from_id": relation.from_id,
            "to_id": relation.to_id
        })
        record = await result.single()
        
        assert record is not None
        assert record["type"] == relation.type
        assert record["from_id"] == relation.from_id
        assert record["to_id"] == relation.to_id


@pytest.mark.asyncio
async def test_should_handle_nonexistent_entities(driver: AsyncDriver):
    """When creating a relation with nonexistent entities, should handle it gracefully"""
    # Arrange
    relation = CreateRelationRequest(
        type="TEST_RELATION",
        from_id="nonexistent_1",
        to_id="nonexistent_2"
    )
    
    # Act
    result = await create_relations_impl(driver, [relation])
    
    # Assert
    assert isinstance(result, CreateRelationsResult)
    assert len(result.result) == 0  # Should return empty result, not error 