from dataclasses import dataclass
from typing import Dict, List, Optional

from neo4j import AsyncDriver
from mcp.server.fastmcp import FastMCP


@dataclass
class Relation:
    type: str
    from_id: str
    to_id: str


@dataclass
class CreateRelationRequest:
    type: str
    from_id: str
    to_id: str


@dataclass
class CreateRelationsResult:
    result: List[Relation]


async def create_relations_impl(driver: AsyncDriver, relations: List[CreateRelationRequest]) -> CreateRelationsResult:
    """Create multiple new relations between entities in the knowledge graph
    
    Args:
        driver: Neo4j async driver instance
        relations: List of relation requests with from_id, to_id, and type fields
        
    Returns:
        CreateRelationsResult containing the created relations
    """
    results = []

    async with driver.session() as session:
        for relation in relations:
            # We need to use string formatting for the relationship type
            # as Neo4j doesn't support parameterized relationship types
            query = f"""
            MATCH (a:Entity {{id: $from_id}}), (b:Entity {{id: $to_id}})
            CREATE (a)-[r:{relation.type}]->(b)
            RETURN type(r) as type, a.id as from_id, b.id as to_id
            """
            params = {
                "from_id": relation.from_id,
                "to_id": relation.to_id
            }

            try:
                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append(Relation(
                        type=record["type"],
                        from_id=record["from_id"],
                        to_id=record["to_id"]
                    ))
            except Exception:
                # If the query fails (e.g., entities not found), continue to next relation
                continue

    return CreateRelationsResult(result=results)


async def register(server: FastMCP, driver: AsyncDriver) -> None:
    """Register the create_relations tool with the MCP server."""
    
    @server.tool("create_relations")
    async def create_relations(relations: List[Dict]) -> Dict:
        """Create multiple new relationships between existing entities in the knowledge graph.
        
        Creates directed relationships between entities. Both source and target entities
        must exist in the database before creating the relationship. The relationship type
        is used as-is (not parameterized) and will be the label of the relationship in Neo4j.
        
        Args:
            relations: List of relation dictionaries, each containing:
                - type: String - The type/label of the relationship (e.g., KNOWS, WORKS_FOR)
                - from: String - ID of the source entity where relationship starts
                - to: String - ID of the target entity where relationship ends
            
        Returns:
            Dict containing:
                result: List of created relationships, each with:
                    - type: String - The relationship type/label
                    - from: String - Source entity ID
                    - to: String - Target entity ID
                    
        Raises:
            ValueError: If required fields are missing
            Neo4jError: If referenced entities don't exist or other database errors
            
        Note:
            - Failed relationship creations (e.g., missing entities) are skipped
            - Relationship types are case sensitive
            - Duplicate relationships between the same entities are allowed
        """
        if "driver" not in server.state:
            raise ValueError("Neo4j driver not found in server state")

        # Convert input dicts to CreateRelationRequest objects
        relation_requests = [
            CreateRelationRequest(
                type=r["type"],
                from_id=r["from"],
                to_id=r["to"]
            ) for r in relations
        ]
        
        result = await create_relations_impl(driver, relation_requests)
        
        # Convert result back to dict format for MCP interface
        return {
            "result": [
                {
                    "type": r.type,
                    "from": r.from_id,
                    "to": r.to_id
                } for r in result.result
            ]
        } 