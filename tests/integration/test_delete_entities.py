import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl
from src.tools.create_relations import create_relations_impl
from src.tools.delete_entities import (
    delete_entities_impl,
    Entity,
    Relationship,
    DeletionResult
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


async def create_test_dataset(driver: AsyncDriver, test_id: str) -> Dict[str, List]:
    """Create a test dataset with various entities and relationships
    
    Args:
        driver: Neo4j async driver instance
        test_id: Unique identifier for this test to ensure data isolation
        
    Returns:
        Dict containing:
        - entities: List[Entity] - The created entities
        - relations: List[Relationship] - The created relationships
    """
    # Create entities with their properties
    john_props = {
        "name": f"John Smith_{test_id}",
        "age": 30,
        "email": f"john_{test_id}@example.com",
        "type": "Person"
    }
    jane_props = {
        "name": f"Jane Smith_{test_id}",
        "age": 28,
        "email": f"jane_{test_id}@example.com",
        "type": "Person"
    }
    company_props = {
        "name": f"Tech Corp_{test_id}",
        "industry": "Technology",
        "type": "Company"
    }
    project_props = {
        "name": f"Project Alpha_{test_id}",
        "status": "Active",
        "type": "Project"
    }
    
    entities = [
        {
            "type": "Person",
            "properties": john_props
        },
        {
            "type": "Person",
            "properties": jane_props
        },
        {
            "type": "Company",
            "properties": company_props
        },
        {
            "type": "Project",
            "properties": project_props
        }
    ]
    
    entity_result = await create_entities_impl(driver, entities)
    created_entities = [
        Entity(
            id=e["id"],
            type=e["type"],
            properties=e["properties"]
        ) for e in entity_result["result"]
    ]
    
    # Create relationships
    relations = [
        {
            "from": created_entities[0].id,  # John
            "to": created_entities[2].id,    # Tech Corp
            "type": "WORKS_AT"
        },
        {
            "from": created_entities[1].id,  # Jane
            "to": created_entities[2].id,    # Tech Corp
            "type": "WORKS_AT"
        },
        {
            "from": created_entities[0].id,  # John
            "to": created_entities[3].id,    # Project Alpha
            "type": "MANAGES"
        }
    ]
    
    relation_result = await create_relations_impl(driver, relations)
    created_relations = [
        Relationship(
            type=r["type"],
            from_id=r["from"],
            to_id=r["to"],
            properties=r.get("properties")
        ) for r in relation_result["result"]
    ]
    
    return {
        "entities": created_entities,
        "relations": created_relations
    }


@pytest.mark.asyncio
async def test_should_delete_entity_without_relationships(driver: AsyncDriver):
    """When deleting an entity without relationships, should delete it successfully"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = {
        "type": "TestEntity",
        "properties": {
            "name": f"Test_{test_id}"
        }
    }
    result = await create_entities_impl(driver, [entity])
    entity_id = result["result"][0]["id"]
    
    # Act
    delete_result = await delete_entities_impl(driver, [entity_id])
    
    # Assert
    assert isinstance(delete_result, DeletionResult)
    assert len(delete_result.deleted_entities) == 1
    assert len(delete_result.deleted_relations) == 0
    assert delete_result.stats["entities_deleted"] == 1
    assert delete_result.stats["relations_deleted"] == 0


@pytest.mark.asyncio
async def test_should_prevent_deletion_with_relationships(driver: AsyncDriver):
    """When deleting an entity with relationships without cascade, should prevent deletion"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    company = next(e for e in data["entities"] if e.type == "Company")
    
    # Act
    result = await delete_entities_impl(driver, [company.id], cascade=False)
    
    # Assert
    assert isinstance(result, DeletionResult)
    assert result.error is not None
    assert len(result.orphaned_relations) == 2  # Two WORKS_AT relationships


@pytest.mark.asyncio
async def test_should_cascade_delete_relationships(driver: AsyncDriver):
    """When deleting with cascade=True, should delete entity and its relationships"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    company = next(e for e in data["entities"] if e.type == "Company")
    
    # Act
    result = await delete_entities_impl(driver, [company.id], cascade=True)
    
    # Assert
    assert isinstance(result, DeletionResult)
    assert len(result.deleted_entities) == 1
    assert len(result.deleted_relations) == 2  # Two WORKS_AT relationships
    assert result.stats["entities_deleted"] == 1
    assert result.stats["relations_deleted"] == 2


@pytest.mark.asyncio
async def test_should_preview_deletion_impact(driver: AsyncDriver):
    """When using dry_run=True, should preview deletion impact without making changes"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    company = next(e for e in data["entities"] if e.type == "Company")
    
    # Act
    preview = await delete_entities_impl(driver, [company.id], dry_run=True)
    
    # Assert
    assert isinstance(preview, DeletionResult)
    assert len(preview.deleted_entities) == 1
    assert len(preview.deleted_relations) == 2
    assert len(preview.orphaned_relations) == 2
    
    # Verify nothing was actually deleted
    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:Entity {id: $id}) RETURN n",
            {"id": company.id}
        )
        assert await result.single() is not None


@pytest.mark.asyncio
async def test_should_handle_multiple_entity_deletion(driver: AsyncDriver):
    """When deleting multiple entities, should handle relationships between them correctly"""
    # Arrange
    test_id = str(uuid.uuid4())
    data = await create_test_dataset(driver, test_id)
    print("\nEntities:", data["entities"])  # Debug output
    
    # Find John's entity and Project entity
    john = next(e for e in data["entities"] if e.type == "Person" and e.properties["name"].startswith("John"))
    project = next(e for e in data["entities"] if e.type == "Project")
    
    # Act
    result = await delete_entities_impl(driver, [john.id, project.id], cascade=True)
    
    # Assert
    assert isinstance(result, DeletionResult)
    assert len(result.deleted_entities) == 2
    assert len(result.deleted_relations) == 2  # WORKS_AT and MANAGES
    assert result.stats["entities_deleted"] == 2
    assert result.stats["relations_deleted"] == 2


@pytest.mark.asyncio
async def test_should_handle_nonexistent_entities(driver: AsyncDriver):
    """When deleting nonexistent entities, should return empty results"""
    # Act
    result = await delete_entities_impl(
        driver,
        ["nonexistent_1", "nonexistent_2"]
    )
    
    # Assert
    assert isinstance(result, DeletionResult)
    assert len(result.deleted_entities) == 0
    assert len(result.deleted_relations) == 0
    assert result.stats["entities_deleted"] == 0
    assert result.stats["relations_deleted"] == 0 