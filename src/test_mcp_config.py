import asyncio
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from typing import Dict, List

async def test_server_connection(server_config: Dict) -> bool:
    """Test connection to an MCP server using the official SDK."""
    try:
        # Create server parameters using the official SDK
        server_params = StdioServerParameters(
            command=server_config['command'][0],  # First command is the executable
            args=server_config['command'][1:],    # Rest are arguments
            env=None  # Use default environment
        )
        
        print(f"Testing server: {server_config['name']}")
        
        # Connect to the stdio server using the official client
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as client:
                # Initialize the connection
                await client.initialize()
                
                # List available tools
                tools = await client.list_tools()
                print(f"Successfully connected to server: {server_config['name']}")
                print(f"Available tools:")
                for tool in tools:
                    name, description = tool
                    print(f"- {name}: {description}")
                
                return True
                
    except Exception as e:
        print(f"Error testing server {server_config['name']}: {str(e)}")
        return False

async def main():
    """Main test function."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    # Load the configuration
    config_path = project_root / "example_mcp_config.json"
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        return
        
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            
        print(f"Successfully loaded MCP configuration with {len(config_data['mcp_servers'])} servers")
        
        # Test each server
        for server in config_data['mcp_servers']:
            success = await test_server_connection(server)
            if success:
                print(f"✅ Server {server['name']} test passed")
            else:
                print(f"❌ Server {server['name']} test failed")
                
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 