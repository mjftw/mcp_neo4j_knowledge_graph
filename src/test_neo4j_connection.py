import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


def test_connection():
    # Load environment variables
    load_dotenv()

    # Get connection details
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    print(f"Attempting to connect to Neo4j at {uri}")
    print(f"Using credentials: {user}")

    try:
        # Create driver
        driver = GraphDatabase.driver(uri, auth=(user, password))

        # Verify connectivity
        driver.verify_connectivity()
        print("Successfully connected to Neo4j!")

        # Test a simple query
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            print(f"Test query result: {record['test']}")

        driver.close()
        print("Connection test completed successfully!")

    except Exception as e:
        print(f"Error connecting to Neo4j: {str(e)}")


if __name__ == "__main__":
    test_connection()
