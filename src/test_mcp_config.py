import asyncio
import json
from pathlib import Path
from typing import Dict, List

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    """Main function for standalone script execution."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent

    # Load the configuration
    config_path = project_root / "example_mcp_config.json"
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        return

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)

        print(
            f"Successfully loaded MCP configuration with {len(config_data['mcp_servers'])} servers"
        )

        # Test each server
        for server in config_data["mcp_servers"]:
            print(f"\nTesting server: {server['name']}")
            try:
                await test_server_connection(server)
                print(f"✅ Server {server['name']} test passed")
            except AssertionError as e:
                print(f"❌ Server {server['name']} test failed: {str(e)}")

    except Exception as e:
        print(f"Error during testing: {str(e)}")


@pytest.fixture
def server_config():
    """Fixture to load the MCP configuration."""
    config_path = Path(__file__).parent.parent / "example_mcp_config.json"
    with open(config_path, "r") as f:
        config_data = json.load(f)
    return config_data["mcp_servers"][0]  # Return first server config


@pytest.mark.asyncio
async def test_server_connection(server_config: Dict) -> None:
    """Test connection to an MCP server using the official SDK."""
    # Create server parameters using the official SDK
    server_params = StdioServerParameters(
        command=server_config["command"][0],  # First command is the executable
        args=server_config["command"][1:],  # Rest are arguments
        env=None,  # Use default environment
    )

    # Connect to the stdio server using the official client
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as client:
            # Initialize the connection
            await client.initialize()

            # List available tools
            tools_result = await client.list_tools()
            tools = tools_result.tools if hasattr(tools_result, "tools") else []
            assert len(tools) > 0, "No tools found"

            # Verify expected tools are present
            tool_names = [tool.name for tool in tools]
            expected_tools = [
                "create_entities",
                "introspect_schema",
                "create_relations",
                "search_entities",
                "update_entities",
                "delete_entities"
            ]
            for tool in expected_tools:
                assert tool in tool_names, f"Expected tool {tool} not found"


if __name__ == "__main__":
    # This section only runs when the script is executed directly
    asyncio.run(main())
