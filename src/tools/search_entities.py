from typing import Any, Dict, List
from neo4j import AsyncDriver


async def search_entities_impl(
    driver: AsyncDriver,
    search_term: str,
    entity_type: str = None,
    properties: List[str] = None,
    include_relationships: bool = False,
    fuzzy_match: bool = True
) -> Dict[str, Any]:
    """Search for entities in the knowledge graph with fuzzy matching support
    
    Args:
        driver: Neo4j async driver instance
        search_term: The text to search for
        entity_type: Optional entity type to filter by
        properties: Optional list of property names to search in (defaults to all)
        include_relationships: Whether to include relationships in results
        fuzzy_match: Whether to use fuzzy matching for text properties
        
    Returns:
        Dict containing the search results
    """
    results = []

    async with driver.session() as session:
        # Build the query dynamically based on parameters
        where_clauses = []
        params = {"search_term": search_term}
        
        # Add type filter if specified
        type_match = "Entity"
        if entity_type:
            type_match += f":{entity_type}"
            
        # Build property matching clause
        if properties:
            property_clauses = []
            words = search_term.split()
            for prop in properties:
                if fuzzy_match:
                    # For each property, check if at least one word matches
                    property_clauses.append(
                        f"({' OR '.join([f'toLower(toString(n.{prop})) CONTAINS toLower($word_{i})' for i, _ in enumerate(words)])})"
                    )
                    # Add each word as a parameter
                    for i, word in enumerate(words):
                        params[f"word_{i}"] = word
                else:
                    property_clauses.append(f"n.{prop} = $search_term")
            if property_clauses:
                # Match if any property matches
                where_clauses.append(f"({' OR '.join(property_clauses)})")
        else:
            # Search all string properties with fuzzy matching
            if fuzzy_match:
                where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] =~ $fuzzy_pattern)")
                params["fuzzy_pattern"] = f"(?i).*{search_term}.*"
            else:
                where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] = $search_term)")

        # Construct the full query
        query = f"""
        MATCH (n:{type_match})
        """
        
        if where_clauses:
            query += f"WHERE {' AND '.join(where_clauses)}\n"

        # Optionally include relationships
        if include_relationships:
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
        
        if include_relationships:
            query += ", rels as relationships"

        # Debug logging
        print(f"Query: {query}")
        print(f"Params: {params}")

        # Execute query
        result = await session.run(query, params)
        
        async for record in result:
            node_data = record["node"]
            if include_relationships:
                node_data["relationships"] = record["relationships"]
            results.append(node_data)

    return {"results": results}


async def register(mcp):
    @mcp.tool(
        name="search_entities",
        description="Search for entities in the knowledge graph with fuzzy matching support"
    )
    async def search_entities(
        search_term: str,
        entity_type: str = None,
        properties: List[str] = None,
        include_relationships: bool = False,
        fuzzy_match: bool = True
    ) -> Dict[str, Any]:
        """Search for entities in the knowledge graph with fuzzy matching support"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")

        return await search_entities_impl(
            mcp.state["driver"],
            search_term,
            entity_type,
            properties,
            include_relationships,
            fuzzy_match
        ) 