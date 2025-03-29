import asyncio
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client


@dataclass
class ServerProcess:
    process: subprocess.Popen
    command: str
    args: list[str]
    env: Optional[Dict[str, str]] = None
    encoding: str = "utf-8"
    encoding_error_handler: str = "strict"


async def main():
    """Test client that connects to the stdio MCP server"""
    print("Starting MCP server process...")
    errors = []

    # Start the server process
    process = subprocess.Popen(
        ["python", "src/server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Create server process wrapper
    server = ServerProcess(
        process=process,
        command="python",
        args=["src/server.py"],
        env=None,  # Use default environment
        encoding="utf-8",
        encoding_error_handler="strict",
    )

    # Connect to the stdio server
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as client:
            # Initialize the connection
            await client.initialize()

            # List available tools
            print("\nAvailable tools:")
            tools = await client.list_tools()
            for tool in tools:
                name, description = tool
                print(f"- {name}: {description}")

            # Test the introspect_schema tool
            print("\nTesting introspect_schema tool...")
            try:
                result = await client.call_tool("introspect_schema", {"random_string": "test"})
                # Access the content from the result
                schema_data = result.content[0].text
                print(f"Schema information:")
                print(schema_data)
            except Exception as e:
                print(f"Error: {e}")
                errors.append(f"introspect_schema failed: {str(e)}")

            # Test the create_entities tool
            print("\nTesting create_entities tool...")
            try:
                result = await client.call_tool(
                    "create_entities",
                    {
                        "entities": [
                            {
                                "type": "Person",
                                "properties": {
                                    "name": "John Doe",
                                    "occupation": "Developer",
                                },
                            }
                        ],
                        "context": {},  # Empty context as required by the schema
                    },
                )
                print(f"Result: {result}")
                if hasattr(result, 'isError') and result.isError:
                    errors.append(f"create_entities failed: {result.content[0].text}")
            except Exception as e:
                print(f"Error: {e}")
                errors.append(f"create_entities failed: {str(e)}")

            # Test the search_entities tool
            print("\nTesting search_entities tool...")
            try:
                search_result = await client.call_tool(
                    "search_entities",
                    {
                        "search_term": "John",
                        "entity_type": "Person",
                        "include_relationships": True,
                        "fuzzy_match": True,
                    },
                )
                print("Search results:")
                if search_result.content:
                    print(search_result.content[0].text)
                else:
                    print("No results found")
            except Exception as e:
                print(f"Error searching entities: {e}")
                errors.append(f"search_entities failed: {str(e)}")

            # Test the update_entities tool
            print("\nTesting update_entities tool...")
            try:
                update_result = await client.call_tool(
                    "update_entities",
                    {
                        "updates": [
                            {
                                "id": "John Doe",  # Assuming this entity exists
                                "properties": {
                                    "occupation": "Senior Developer",
                                    "years_experience": 5
                                },
                                "add_labels": ["Employee"]
                            }
                        ]
                    }
                )
                print("Update results:")
                if update_result.content:
                    print(update_result.content[0].text)
                else:
                    print("No updates performed")
                if hasattr(update_result, 'isError') and update_result.isError:
                    errors.append(f"update_entities failed: {update_result.content[0].text}")
            except Exception as e:
                print(f"Error updating entities: {e}")
                errors.append(f"update_entities failed: {str(e)}")

            # Test the delete_entities tool
            print("\nTesting delete_entities tool...")
            try:
                delete_result = await client.call_tool(
                    "delete_entities",
                    {
                        "entity_ids": ["John Doe"],  # Assuming this entity exists
                        "cascade": True
                    }
                )
                print("Delete results:")
                if delete_result.content:
                    print(delete_result.content[0].text)
                else:
                    print("No deletions performed")
                if hasattr(delete_result, 'isError') and delete_result.isError:
                    errors.append(f"delete_entities failed: {delete_result.content[0].text}")
            except Exception as e:
                print(f"Error deleting entities: {e}")
                errors.append(f"delete_entities failed: {str(e)}")

            # Clean up
            process.terminate()
            await asyncio.sleep(0.1)  # Give process time to terminate
            process.kill()  # Force kill if still running

            # Report test results
            if errors:
                print("\nTest failed with the following errors:")
                for error in errors:
                    print(f"- {error}")
                sys.exit(1)
            else:
                print("\nTest completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
