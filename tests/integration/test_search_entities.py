import uuid
from typing import AsyncGenerator, Dict, List

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.tools.create_entities import create_entities_impl, CreateEntityRequest
from src.tools.create_relations import create_relations_impl, CreateRelationRequest
from src.tools.search_entities import search_entities_impl, SearchEntityRequest


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
    created_relations = relation_result.result
    
    return {
        "entities": created_entities,
        "relations": created_relations
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
        SearchEntityRequest(
            search_term=f"John Smith_{test_id}",
            fuzzy_match=False
        )
    )
    
    # Assert
    assert len(result.results) == 1
    assert result.results[0].properties["name"] == f"John Smith_{test_id}"


@pytest.mark.asyncio
async def test_should_find_multiple_entities_with_fuzzy_name_match(driver: AsyncDriver):
    """When searching with fuzzy name match, should return all partially matching entities"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"Smith_{test_id}",
            fuzzy_match=True
        )
    )
    
    # Assert
    assert len(result.results) == 2
    assert all("Smith" in entity.properties["name"] for entity in result.results)


@pytest.mark.asyncio
async def test_should_filter_entities_by_type(driver: AsyncDriver):
    """When filtering by entity type, should return only entities of that type"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=test_id,
            entity_type="Person",
            fuzzy_match=True
        )
    )
    
    # Assert
    assert len(result.results) == 2
    assert all("Person" in entity.type for entity in result.results)


@pytest.mark.asyncio
async def test_should_find_entity_by_property_value(driver: AsyncDriver):
    """When searching by specific property value, should return matching entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"john_{test_id}@example.com",
            properties=["email"]
        )
    )
    
    # Assert
    assert len(result.results) == 1
    assert result.results[0].properties["email"] == f"john_{test_id}@example.com"


@pytest.mark.asyncio
async def test_should_include_relationships_when_requested(driver: AsyncDriver):
    """When relationships are included, should return entity with its relationships"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"John Smith_{test_id}",
            include_relationships=True
        )
    )
    
    # Assert
    assert len(result.results) == 1
    entity = result.results[0]
    assert entity.properties["name"] == f"John Smith_{test_id}"
    assert len(entity.relationships) == 2
    assert any(rel["type"] == "WORKS_AT" for rel in entity.relationships)
    assert any(rel["type"] == "MANAGES" for rel in entity.relationships)


@pytest.mark.asyncio
async def test_should_return_empty_results_for_nonexistent_entity(driver: AsyncDriver):
    """When searching for nonexistent entity, should return empty results"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"NonexistentPerson_{test_id}"
        )
    )
    
    # Assert
    assert len(result.results) == 0


@pytest.mark.asyncio
async def test_should_match_case_insensitively(driver: AsyncDriver):
    """When searching with different case, should match case-insensitively"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)
    
    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"john smith_{test_id}",  # lowercase
            fuzzy_match=True
        )
    )
    
    # Assert
    assert len(result.results) == 1
    assert result.results[0].properties["name"] == f"John Smith_{test_id}"


@pytest.mark.asyncio
async def test_should_find_entity_by_exact_name(driver: AsyncDriver):
    """When searching for entity by exact name, should return matching entity with properties"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)

    # Act
    result = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=f"Tech Corp_{test_id}",
            properties=["name"],
            fuzzy_match=False
        )
    )

    # Assert
    assert len(result.results) == 1
    assert result.results[0].properties["name"] == f"Tech Corp_{test_id}"
    assert "Company" in result.results[0].type


@pytest.mark.asyncio
async def test_should_find_entity_by_type_and_property(driver: AsyncDriver):
    """When searching with type and property filters, should return only matching entity"""
    # Arrange
    test_id = str(uuid.uuid4())
    await create_test_dataset(driver, test_id)

    # Act
    results = await search_entities_impl(
        driver,
        SearchEntityRequest(
            search_term=test_id,
            entity_type="Company",
            properties=["name"],
            fuzzy_match=True
        )
    )

    # Assert
    assert len(results.results) == 1
    assert "Company" in results.results[0].type
    assert test_id in results.results[0].properties["name"] 