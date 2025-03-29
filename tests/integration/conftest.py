import pytest
from typing import AsyncGenerator
from neo4j import AsyncDriver, AsyncGraphDatabase


@pytest.fixture
async def driver() -> AsyncGenerator[AsyncDriver, None]:
    """Common fixture providing a Neo4j driver for all integration tests"""
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    
    try:
        await driver.verify_connectivity()
        yield driver
    finally:
        await driver.close()


@pytest.fixture(autouse=True)
async def clean_database(driver: AsyncDriver):
    """Automatically clean the database before each test"""
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n") 