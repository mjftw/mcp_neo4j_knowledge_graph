import asyncio
import subprocess
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
                result = await client.call_tool("introspect_schema", {})
                # Access the content from the result
                schema_data = result.content[0].text
                print(f"Schema information:")
                print(schema_data)
            except Exception as e:
                print(f"Error: {e}")

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
            except Exception as e:
                print(f"Error: {e}")

            print("\nTest completed successfully!")

            # Clean up
            process.terminate()
            await asyncio.sleep(0.1)  # Give process time to terminate
            process.kill()  # Force kill if still running


if __name__ == "__main__":
    asyncio.run(main())
