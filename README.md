# Script Runner Web Server

This project provides a simple Python web server that executes commands based on incoming JSON requests and handles temporary file management.

## Docker Setup and Usage

To run this server in a Docker container, follow these steps:

1.  **Build the Docker Image:**

    ```bash
    docker build -t script-runner .
    ```

2.  **Run the Docker Container:**

    To run the container with support for custom scripts, you need to mount a directory from your host to the container and provide the `ECUI_CONFIG_PATH` environment variable.

    ```bash
    docker run \
      -v /path/to/your/config:/config \
      -e ECUI_CONFIG_PATH=/config \
      --network host \
      script-runner
    ```

    - `-v /path/to/your/config:/config`: This mounts a directory from your host machine (e.g., `/path/to/your/config`) to the `/config` directory inside the container. Your custom scripts should be placed in a `scripts` subdirectory within this mounted volume (e.g., `/path/to/your/config/scripts`).
    - `-e ECUI_CONFIG_PATH=/config`: This environment variable tells the server where to look for custom scripts.

### Convenience Script

For convenience, a script is provided to automate the build and run steps:

```bash
./launch_script_runner.sh
```

This script will also stop and remove any existing container from a previous launch. You may need to modify this script to include your custom volume mounts and environment variables.

## API Endpoints

### `ScriptConfig` Typedef

This is the structure expected for the JSON payload sent to the `/execute` endpoint (any additional properties are ignored):

```typescript
/**
 * @typedef {Object} ScriptConfig
 * @property {string} command - The command to be executed (e.g., "python", "node", "bash", or a script name from the configured scripts directory).
 * @property {Array<string | {type: "tmp-file-path", download: boolean, downloadName: string}>} args - An array of arguments to pass to the command.
 *   - `string`: A literal string argument.
 *   - `{type: "tmp-file-path", download: boolean, downloadName: string}`: Instructs the server to generate a temporary file path.
 *   - `download`: If `true`, the temporary file will be made available for download after command execution.
 *   - `downloadName`: The suggested filename for download if `download` is `true`.
 */
```

### `POST /execute`

- **Description**: Executes a command specified in the `ScriptConfig`.
- **Request Method**: `POST`
- **Request URL**: `/execute`
- **Request Headers**:
  - `Content-Type: application/json`
- **Request Body**: A JSON object conforming to the `ScriptConfig` typedef.
  - **Example Request Body**:
    ```json
    {
      "id": "my-script-1",
      "title": "Run a simple Python script",
      "command": "python",
      "args": [
        "-c",
        "import sys; print('Hello from Python'); print('Args:', sys.argv[1:]); f=open(sys.argv[1],'w'); f.write('Temporary file content'); f.close();",
        {
          "type": "tmp-file-path",
          "download": true,
          "downloadName": "output.txt"
        }
      ]
    }
    ```
- **Response**: The server streams the `stdout` and `stderr` of the executed command as plain text. If any `tmp-file-path` arguments were marked with `"download": true`, a JSON object containing download information will be appended to the streamed output, prefixed by `\n---DOWNLOAD-INFO---\n`.
  - **Example Download Info Appended to Output**:
    ```json
    {
      "temp_files": [
        {
          "download_url": "/download/tmp12345.txt",
          "download_name": "output.txt"
        }
      ]
    }
    ```

### `GET /download/<filename>`

- **Description**: Downloads a temporary file that was generated during a script execution and marked for download.
- **Request Method**: `GET`
- **Request URL**: `/download/<filename>` (e.g., `/download/tmp12345.txt`)
- **Parameters**:
  - `<filename>`: The actual filename of the temporary file to download. This name is provided in the `download_url` from the `/execute` response.
- **Response**: The content of the requested temporary file as `application/octet-stream` with a `Content-Disposition` header suggesting the original `downloadName` if provided during the `/execute` request. If the file is not found, a `404 Not Found` error is returned.
