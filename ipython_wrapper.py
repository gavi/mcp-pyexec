import sys
import json
from IPython import get_ipython
from IPython.display import display, Image
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from contextlib import redirect_stdout, redirect_stderr

def execute_code(code):
    output = []
    
    ipython = get_ipython()
    if ipython is None:
        from IPython.core.interactiveshell import InteractiveShell
        ipython = InteractiveShell.instance()

    # Capture stdout and stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        result = ipython.run_cell(code)

    # Handle text output
    if result.result is not None:
        output.append({"type": "text", "data": str(result.result)})

    # Handle captured stdout
    stdout_output = stdout_capture.getvalue()
    if stdout_output:
        output.append({"type": "text", "data": stdout_output})

    # Handle captured stderr
    stderr_output = stderr_capture.getvalue()
    if stderr_output:
        output.append({"type": "error", "data": stderr_output})

    # Handle plots
    if plt.get_fignums():
        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)
        img_base64 = base64.b64encode(img_data.getvalue()).decode()
        output.append({"type": "image", "data": img_base64})
        plt.close()

    # Handle errors
    if result.error_before_exec or result.error_in_exec:
        error_message = str(result.error_before_exec or result.error_in_exec)
        output.append({"type": "error", "data": error_message})

    return output

if __name__ == "__main__":
    code = sys.stdin.read()
    result = execute_code(code)
    print(json.dumps(result))