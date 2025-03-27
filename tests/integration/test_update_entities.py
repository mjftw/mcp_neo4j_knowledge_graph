import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl, CreateEntityRequest
from src.tools.update_entities import (
    update_entities_impl,
    UpdateEntityRequest
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


async def create_test_entity(driver: AsyncDriver, test_id: str) -> Dict:
    """Create a test entity for update tests"""
    entity = CreateEntityRequest(
        type="TestEntity",
        properties={
            "name": f"Test_{test_id}",
            "count": 1,
            "tags": ["test", "initial"]
        }
    )
    
    result = await create_entities_impl(driver, [entity])
    return result.result[0].__dict__


@pytest.mark.asyncio
async def test_should_update_entity_properties(driver: AsyncDriver):
    """When updating entity properties, should modify existing and add new ones"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = await create_test_entity(driver, test_id)
    
    # Act
    update = UpdateEntityRequest(
        id=entity["id"],
        properties={
            "count": 2,  # Modify existing
            "description": "New property"  # Add new
        }
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 1
    updated = result.updated_entities[0]
    assert updated.properties["count"] == 2
    assert updated.properties["description"] == "New property"
    assert updated.properties["name"] == f"Test_{test_id}"  # Unchanged


@pytest.mark.asyncio
async def test_should_remove_entity_properties(driver: AsyncDriver):
    """When removing properties, should remove them from the entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = await create_test_entity(driver, test_id)
    
    # Act
    update = UpdateEntityRequest(
        id=entity["id"],
        remove_properties=["count", "tags"]
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 1
    updated = result.updated_entities[0]
    assert "count" not in updated.properties
    assert "tags" not in updated.properties
    assert "name" in updated.properties  # Unchanged


@pytest.mark.asyncio
async def test_should_add_entity_labels(driver: AsyncDriver):
    """When adding labels, should append them to entity's type list"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = await create_test_entity(driver, test_id)
    
    # Act
    update = UpdateEntityRequest(
        id=entity["id"],
        add_labels=["NewLabel", "AnotherLabel"]
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 1
    updated = result.updated_entities[0]
    assert "NewLabel" in updated.type
    assert "AnotherLabel" in updated.type
    assert "TestEntity" in updated.type  # Original label remains


@pytest.mark.asyncio
async def test_should_remove_entity_labels(driver: AsyncDriver):
    """When removing labels, should remove them from entity's type list"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = await create_test_entity(driver, test_id)
    
    # First add some labels to remove
    await update_entities_impl(
        driver,
        [UpdateEntityRequest(id=entity["id"], add_labels=["ToRemove1", "ToRemove2", "ToKeep"])]
    )
    
    # Act
    update = UpdateEntityRequest(
        id=entity["id"],
        remove_labels=["ToRemove1", "ToRemove2"]
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 1
    updated = result.updated_entities[0]
    assert "ToRemove1" not in updated.type
    assert "ToRemove2" not in updated.type
    assert "ToKeep" in updated.type
    assert "TestEntity" in updated.type


@pytest.mark.asyncio
async def test_should_handle_batch_updates(driver: AsyncDriver):
    """When updating multiple entities, should process all updates"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity1 = await create_test_entity(driver, f"{test_id}_1")
    entity2 = await create_test_entity(driver, f"{test_id}_2")
    
    # Act
    updates = [
        UpdateEntityRequest(
            id=entity1["id"],
            properties={"status": "updated"}
        ),
        UpdateEntityRequest(
            id=entity2["id"],
            properties={"status": "updated"}
        )
    ]
    result = await update_entities_impl(driver, updates)
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 2
    assert all(e.properties["status"] == "updated" for e in result.updated_entities)


@pytest.mark.asyncio
async def test_should_handle_nonexistent_entity(driver: AsyncDriver):
    """When updating nonexistent entity, should return error"""
    # Act
    update = UpdateEntityRequest(
        id="nonexistent",
        properties={"test": "value"}
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert not result.success
    assert len(result.updated_entities) == 0
    assert result.errors
    assert "not found" in result.errors[0]


@pytest.mark.asyncio
async def test_should_handle_combined_updates(driver: AsyncDriver):
    """When combining different types of updates, should apply all changes"""
    # Arrange
    test_id = str(uuid.uuid4())
    entity = await create_test_entity(driver, test_id)
    
    # Act
    update = UpdateEntityRequest(
        id=entity["id"],
        properties={"status": "active"},
        remove_properties=["count"],
        add_labels=["Active"],
        remove_labels=["TestEntity"]
    )
    result = await update_entities_impl(driver, [update])
    
    # Assert
    assert result.success
    assert len(result.updated_entities) == 1
    updated = result.updated_entities[0]
    assert updated.properties["status"] == "active"
    assert "count" not in updated.properties
    assert "Active" in updated.type
    assert "TestEntity" not in updated.type 