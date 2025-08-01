import asyncio
import uuid
import traceback
import logging
import json
from fastmcp import FastMCP, Context
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent, ImageContent
from fastmcp.server.auth import BearerAuthProvider

auth = BearerAuthProvider(
    jwks_uri="https://idp.objectgraph.com/.well-known/jwks.json",
    algorithm="ES256",
    issuer="https://idp.objectgraph.com"
)

# Initialize FastMCP server for IPython execution
mcp = FastMCP("ipython-executor", auth=auth)


# IPython execution constants
PROCESS_TIMEOUT_SECONDS = 30  # Maximum execution time for IPython code
MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB maximum output size

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def kill_process_tree(process):
    """Kill a process and all its children."""
    try:
        # Create process to kill the docker container
        kill_process = await asyncio.create_subprocess_exec(
            'docker', 'kill', process.args[2],  # process.args[2] contains container ID
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await kill_process.communicate()
    except Exception as e:
        logger.error(f"Error killing process: {str(e)}")

async def execute_with_timeout(process, code: str, timeout: int):
    """Execute the code with a timeout and handle cleanup."""
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=code.encode()),
            timeout=timeout
        )
        return stdout, stderr, process.returncode
    except asyncio.TimeoutError:
        await kill_process_tree(process)
        raise Exception(f"Process exceeded maximum execution time of {timeout} seconds")

@mcp.tool()
async def execute_python(ctx: Context, code: str) -> ToolResult:
    """Execute Python code in a Docker container with IPython-like behavior
    
    This tool allows execution of arbitrary Python code in a secure Docker container.
    The code runs with resource limits and network isolation for safety.
    All the code including imports should be in one code.
    
    Args:
        code: Python code to execute (supports multi-line code, imports, data analysis, etc.)
        
    Returns:
        Execution results including output, errors, and any generated data
        
    Examples:
        - execute_python("print('Hello World')")
        - execute_python("import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df)")
        - execute_python("import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()")
    """
    try:
        # Log incoming bearer token for debugging
        try:
            request = ctx.get_http_request()
            auth_header = request.headers.get("authorization", "No Authorization header")
            logger.info(f"=== AUTH DEBUG ===")
            logger.info(f"Authorization header: {auth_header}")
            
            # Log all headers
            headers_dict = dict(request.headers)
            logger.info(f"All headers: {headers_dict}")
            
            # Log client info
            if request.client:
                logger.info(f"Client IP: {request.client.host}")
            logger.info(f"Request URL: {request.url}")
            logger.info(f"Request method: {request.method}")
            logger.info(f"=== END AUTH DEBUG ===")
        except Exception as e:
            logger.error(f"Error getting request info: {str(e)}")

        if not code or not code.strip():
            return ToolResult(content=[TextContent(type="text", text="Error: No Python code provided")])

        logger.info(f"Received Python execution request")

        # Generate a unique container name
        container_name = f"ipython-exec-{uuid.uuid4()}"

        # Prepare docker run command arguments
        docker_args = [
            'docker', 'run',
            '--name', container_name,
            '--rm',
            '--memory', '512m',
            '--cpus', '0.5',
            '--network', 'none',  # Disable network access for security
            '-i',
        ]


        # Use the custom IPython executor image
        docker_args.append('ipython-executor')

        # Run the code in a new container with resource limits
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr, returncode = await execute_with_timeout(
                process, 
                code,  # Send the code via stdin to the wrapper
                PROCESS_TIMEOUT_SECONDS
            )

            # Check output size
            if len(stdout) > MAX_OUTPUT_SIZE or len(stderr) > MAX_OUTPUT_SIZE:
                return ToolResult(content=[TextContent(type="text", text="Error: Output size exceeds maximum limit")])

            if returncode == 0:
                try:
                    # Parse the JSON result from the IPython wrapper
                    output_str = stdout.decode('utf-8', errors='replace').strip()
                    result = json.loads(output_str)
                    
                    # Check if there are any images in the result
                    images = [item for item in result if item.get("type") == "image"]
                    text_outputs = [item for item in result if item.get("type") in ["text", "error"]]
                    
                    # Format text output
                    text_content = ""
                    for item in text_outputs:
                        if item["type"] == "text":
                            text_content += item["data"]
                        elif item["type"] == "error":
                            text_content += f"ERROR: {item['data']}\n"
                    
                    # Build content list for ToolResult
                    content = []
                    
                    # Add text content if present
                    if text_content.strip():
                        content.append(TextContent(type="text", text=text_content.strip()))
                    
                    # Add images if present
                    for img_item in images:
                        content.append(ImageContent(
                            type="image",
                            data=img_item["data"],  # Keep as base64 string
                            mimeType="image/png"
                        ))
                    
                    # If no content, add a success message
                    if not content:
                        content.append(TextContent(type="text", text="✓ Execution successful (no output)"))
                    
                    return ToolResult(content=content)
                        
                except json.JSONDecodeError:
                    # Fallback to raw output if JSON parsing fails
                    output = stdout.decode('utf-8', errors='replace')
                    return ToolResult(content=[TextContent(type="text", text=f"✓ Execution completed:\n\n```\n{output}\n```")])
            else:
                error_output = stderr.decode('utf-8', errors='replace')
                return ToolResult(content=[TextContent(type="text", text=f"✗ Docker execution failed:\n\n```\n{error_output}\n```")])

        except Exception as e:
            if "exceeded maximum execution time" in str(e):
                return ToolResult(content=[TextContent(type="text", text=f"✗ Execution timed out after {PROCESS_TIMEOUT_SECONDS} seconds")])
            else:
                logger.error(f"Error executing Python code: {str(e)}")
                return ToolResult(content=[TextContent(type="text", text=f"✗ Error executing code: {str(e)}")])

    except Exception as e:
        logger.error(f"Error in execute_python: {str(e)}")
        logger.error(traceback.format_exc())
        return ToolResult(content=[TextContent(type="text", text=f"✗ Error: {str(e)}")])

if __name__ == "__main__":
    mcp.run()