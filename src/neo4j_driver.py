from neo4j import AsyncDriver, AsyncGraphDatabase


async def create_neo4j_driver(
    uri: str = "neo4j://localhost:7687",
    username: str = "neo4j",
    password: str = "password"
) -> AsyncDriver:
    """Create an async Neo4j driver with the given configuration.
    
    Args:
        uri: Neo4j connection URI (default: bolt://localhost:7687)
        username: Neo4j username (default: neo4j)
        password: Neo4j password (default: password)
        
    Returns:
        AsyncDriver: Configured Neo4j driver instance
        
    Raises:
        Exception: If connection verification fails
    """
    driver = AsyncGraphDatabase.driver(
        uri,
        auth=(username, password)
    )
    
    # Verify connectivity before returning
    await driver.verify_connectivity()
    return driver 