import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl, CreateEntityRequest
from src.tools.create_relations import create_relations_impl, CreateRelationRequest
from src.tools.delete_entities import (
    delete_entities_impl,
    DeleteEntityRequest
)


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
        
    Returns:
        Dict containing:
        - entities: List[Dict] - The created entities
        - relations: List[Dict] - The created relationships
    """
    # Create entities
    entities = [
        CreateEntityRequest(
            type="Person",
            properties={
                "name": f"John Smith_{test_id}",
                "age": 30,
                "email": f"john_{test_id}@example.com"
            }
        ),
        CreateEntityRequest(
            type="Person",
            properties={
                "name": f"Jane Smith_{test_id}",
                "age": 28,
                "email": f"jane_{test_id}@example.com"
            }
        ),
        CreateEntityRequest(
            type="Company",
            properties={
                "name": f"Tech Corp_{test_id}",
                "industry": "Technology"
            }
        ),
        CreateEntityRequest(
            type="Project",
            properties={
                "name": f"Project Alpha_{test_id}",
                "status": "Active"
            }
        )
    ]
    
    entity_result = await create_entities_impl(driver, entities)
    created_entities = entity_result.result
    
    # Create relationships
    relations = [
        CreateRelationRequest(
            type="WORKS_AT",
            from_id=created_entities[0].id,  # John
            to_id=created_entities[2].id     # Tech Corp
        ),
        CreateRelationRequest(
            type="WORKS_AT",
            from_id=created_entities[1].id,  # Jane
            to_id=created_entities[2].id     # Tech Corp
        ),
        CreateRelationRequest(
            type="MANAGES",
            from_id=created_entities[0].id,  # John
            to_id=created_entities[3].id     # Project Alpha
        )
    ]
    
    relation_result = await create_relations_impl(driver, relations)
    
    return {
        "entities": [e.__dict__ for e in created_entities],
        "relations": [r.__dict__ for r in relation_result.result]
    }


@pytest.mark.asyncio
async def test_should_delete_entity_without_relationships(driver: AsyncDriver):
    """When deleting an entity without relationships, should delete it successfully"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = CreateEntityRequest(
        type="TestEntity",
        properties={
            "name": f"Test_{test_id}"
        }
    )
    result = await create_entities_impl(driver, [entity])
    entity_id = result.result[0].id
    
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id=entity_id)]
    )
    
    # Assert
    assert delete_result.success
    assert len(delete_result.deleted_entities) == 1
    assert delete_result.deleted_entities[0].id == entity_id


@pytest.mark.asyncio
async def test_should_prevent_deletion_with_relationships(driver: AsyncDriver):
    """When deleting an entity with relationships without cascade, should prevent deletion"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    entity_id = data["entities"][0]["id"]  # John Smith has relationships
    
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id=entity_id)]
    )
    
    # Assert
    assert not delete_result.success
    assert len(delete_result.errors) > 0
    assert "orphaned relationships" in delete_result.errors[0]


@pytest.mark.asyncio
async def test_should_cascade_delete_relationships(driver: AsyncDriver):
    """When deleting with cascade=True, should delete entity and its relationships"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    entity_id = data["entities"][0]["id"]  # John Smith has relationships
    
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id=entity_id, cascade=True)]
    )
    
    # Assert
    assert delete_result.success
    assert len(delete_result.deleted_entities) == 1
    assert delete_result.deleted_entities[0].id == entity_id
    assert len(delete_result.deleted_relationships) > 0


@pytest.mark.asyncio
async def test_should_preview_deletion_impact(driver: AsyncDriver):
    """When using dry_run=True, should preview deletion impact without making changes"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    entity_id = data["entities"][0]["id"]  # John Smith has relationships
    
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id=entity_id, cascade=True)],
        dry_run=True
    )
    
    # Assert
    assert delete_result.success
    assert len(delete_result.impacted_entities) > 0
    assert len(delete_result.impacted_relationships) > 0
    assert len(delete_result.deleted_entities) == 0
    assert len(delete_result.deleted_relationships) == 0


@pytest.mark.asyncio
async def test_should_handle_multiple_entity_deletion(driver: AsyncDriver):
    """When deleting multiple entities, should handle relationships between them correctly"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    entity_ids = [data["entities"][0]["id"], data["entities"][1]["id"]]  # John and Jane
    
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id=id, cascade=True) for id in entity_ids]
    )
    
    # Assert
    assert delete_result.success
    assert len(delete_result.deleted_entities) == 2
    assert all(e.id in entity_ids for e in delete_result.deleted_entities)
    assert len(delete_result.deleted_relationships) > 0


@pytest.mark.asyncio
async def test_should_handle_nonexistent_entities(driver: AsyncDriver):
    """When deleting nonexistent entities, should handle gracefully"""
    # Act
    delete_result = await delete_entities_impl(
        driver,
        [DeleteEntityRequest(id="nonexistent")]
    )
    
    # Assert
    assert not delete_result.success
    assert len(delete_result.errors) > 0
    assert "not found" in delete_result.errors[0] 