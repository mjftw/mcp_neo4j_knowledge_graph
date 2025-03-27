from typing import Any, Dict, List, Optional
from neo4j import AsyncDriver
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP


@dataclass
class SearchEntityRequest:
    """Request to search for entities"""
    search_term: str
    entity_type: Optional[str] = None
    properties: Optional[List[str]] = None
    include_relationships: bool = False
    fuzzy_match: bool = True


@dataclass
class Entity:
    """Represents a Neo4j entity with its properties"""
    id: str
    type: List[str]
    properties: Dict[str, any]
    relationships: Optional[List[Dict[str, any]]] = None


@dataclass
class SearchEntitiesResult:
    """Result of searching for entities"""
    results: List[Entity]


async def search_entities_impl(driver: AsyncDriver, search_request: SearchEntityRequest) -> SearchEntitiesResult:
    """Search for entities in the knowledge graph with fuzzy matching support
    
    Args:
        driver: Neo4j async driver instance
        search_request: Search parameters including query and filters
        
    Returns:
        SearchEntitiesResult containing matching entities
    """
    results = []

    async with driver.session() as session:
        # Build the query dynamically based on parameters
        where_clauses = []
        params = {"search_term": search_request.search_term}
        
        # Add type filter if specified
        type_match = "Entity"
        if search_request.entity_type:
            type_match += f":{search_request.entity_type}"
            
        # Build property matching clause
        if search_request.properties:
            property_clauses = []
            words = search_request.search_term.split()
            for prop in search_request.properties:
                if search_request.fuzzy_match:
                    # For each property, check if at least one word matches
                    property_clauses.append(
                        f"({' OR '.join([f'toLower(toString(n.{prop})) CONTAINS toLower($word_{i})' for i, _ in enumerate(words)])})"
                    )
                    # Add each word as a parameter
                    for i, word in enumerate(words):
                        params[f"word_{i}"] = word
                else:
                    property_clauses.append(f"n.{prop} = '{search_request.search_term}'")
            if property_clauses:
                where_clauses.append(f"({' OR '.join(property_clauses)})")
        else:
            # Search all string properties with fuzzy matching
            if search_request.fuzzy_match:
                where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] =~ $fuzzy_pattern)")
                params["fuzzy_pattern"] = f"(?i).*{search_request.search_term}.*"
            else:
                where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] = $search_term)")

        # Construct the full query
        query = f"""
        MATCH (n:{type_match})
        """
        
        if where_clauses:
            query += f"WHERE {' AND '.join(where_clauses)}\n"

        # Optionally include relationships
        if search_request.include_relationships:
            query += """
            OPTIONAL MATCH (n)-[r]-(related)
            WITH n, collect({type: type(r), direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END, 
                           node: {id: related.id, type: labels(related)[0], properties: properties(related)}}) as rels
            """
        
        query += """
        RETURN {
            id: n.id,
            type: labels(n),
            properties: properties(n)
        } as node
        """
        
        if search_request.include_relationships:
            query += ", rels as relationships"

        # Debug logging
        print(f"Query: {query}")
        print(f"Params: {params}")

        # Execute query
        result = await session.run(query, params)
        
        async for record in result:
            node_data = record["node"]
            if search_request.include_relationships:
                node_data["relationships"] = record["relationships"]
            
            # Convert to Entity dataclass
            results.append(Entity(
                id=node_data["id"],
                type=node_data["type"],
                properties=node_data["properties"],
                relationships=node_data.get("relationships")
            ))

    return SearchEntitiesResult(results=results)


async def register(server: FastMCP, driver: AsyncDriver) -> None:
    """Register the search_entities tool with the MCP server."""
    
    @server.tool("search_entities")
    async def search_entities(
        search_term: str,
        entity_type: Optional[str] = None,
        properties: Optional[List[str]] = None,
        include_relationships: bool = False,
        fuzzy_match: bool = True
    ) -> Dict[str, Any]:
        """Search for entities in the knowledge graph with fuzzy matching support"""
        
        search_request = SearchEntityRequest(
            search_term=search_term,
            entity_type=entity_type,
            properties=properties,
            include_relationships=include_relationships,
            fuzzy_match=fuzzy_match
        )
        
        result = await search_entities_impl(driver, search_request)
        
        # Convert result back to dict format for MCP interface
        return {
            "results": [
                {
                    "id": entity.id,
                    "type": entity.type,
                    "properties": entity.properties,
                    **({"relationships": entity.relationships} if entity.relationships else {})
                } for entity in result.results
            ]
        } 