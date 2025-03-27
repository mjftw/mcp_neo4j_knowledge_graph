from typing import Dict, List
from neo4j import AsyncDriver


async def create_relations_impl(driver: AsyncDriver, relations: List[Dict]) -> Dict:
    """Create multiple new relations between entities in the knowledge graph
    
    Args:
        driver: Neo4j async driver instance
        relations: List of relation dictionaries with from, to, and type fields
        
    Returns:
        Dict containing the created relations
    """
    results = []

    async with driver.session() as session:
        for relation in relations:
            # We need to use string formatting for the relationship type
            # as Neo4j doesn't support parameterized relationship types
            query = f"""
            MATCH (a:Entity {{id: $from}}), (b:Entity {{id: $to}})
            CREATE (a)-[r:{relation['type']}]->(b)
            RETURN type(r) as type, a.id as from_id, b.id as to_id
            """
            params = {
                "from": relation["from"],
                "to": relation["to"]
            }

            try:
                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append(
                        {
                            "type": record["type"],
                            "from": record["from_id"],
                            "to": record["to_id"],
                        }
                    )
            except Exception:
                # If the query fails (e.g., entities not found), continue to next relation
                continue

    return {"result": results}


async def register(mcp, driver: AsyncDriver):
    @mcp.tool(
        name="create_relations",
        description="Create multiple new relations between entities"
    )
    async def create_relations(relations: List[Dict]) -> Dict:
        """Create multiple new relations between entities"""

        return await create_relations_impl(driver, relations) 