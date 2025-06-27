import shutil
import http.server
import json
import os
import socketserver
import subprocess
import tempfile
from http import HTTPStatus
from pathlib import Path
import threading

TEMP_DIR = Path(tempfile.gettempdir())
CONFIG_PATH = Path(os.environ.get("ECUI_CONFIG_PATH", "/config"))
SCRIPTS_DIR = CONFIG_PATH / "scripts"
TIMEOUT_SECONDS = 5  # 15 minutes timeout for script execution
with open(CONFIG_PATH / "config.json") as f:
    config_json = json.load(f)
PORT = config_json.get("SCRIPT_RUNNER", {}).get("port", 8000)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/execute":
            self.execute_script()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_GET(self):
        if self.path.startswith("/download/"):
            self.download_file()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def execute_script(self):
        try:
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            config = json.loads(post_data)

            command = config.get("command")
            args = config.get("args", [])

            if not command:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(b"Missing 'command' in request body")
                return

            command_path = shutil.which(command)
            if not command_path:
                script_path = SCRIPTS_DIR / command
                if script_path.is_file():
                    command_path = str(script_path)
                else:
                    self.send_response(HTTPStatus.BAD_REQUEST)
                    self.end_headers()
                    self.wfile.write(f"Command not found: {command}".encode("utf-8"))
                    return

            processed_args = []
            temp_files = []
            for arg in args:
                if isinstance(arg, dict) and arg.get("type") == "tmp-file-path":
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, dir=TEMP_DIR)
                    tmp_file.close()
                    processed_args.append(tmp_file.name)
                    temp_files.append(
                        {
                            "path": tmp_file.name,
                            "download": arg.get("download", False),
                            "downloadName": arg.get("downloadName"),
                        }
                    )
                else:
                    processed_args.append(str(arg))

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()

            self.wfile.write(
                f"Executing: {command_path} {' '.join(processed_args)}\n".encode(
                    "utf-8"
                )
            )
            self.wfile.flush()

            process = subprocess.Popen(
                [command_path] + processed_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            def stream_output(pipe, wfile):
                for line in iter(pipe.readline, ""):
                    wfile.write(line.encode("utf-8"))
                    wfile.flush()
                pipe.close()

            output_thread = threading.Thread(
                target=stream_output, args=(process.stdout, self.wfile)
            )
            output_thread.start()

            try:
                process.wait(timeout=TIMEOUT_SECONDS)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                self.wfile.write(
                    f"\n---PROCESS-TIMEOUT---\nProcess exceeded time limit of {TIMEOUT_SECONDS} seconds and was terminated.\n".encode("utf-8")
                )
                self.wfile.flush()
                exit_code = -1

            output_thread.join()

            if temp_files and exit_code == 0:
                download_info = {"temp_files": []}
                for f in temp_files:
                    if f["download"]:
                        download_info["temp_files"].append(
                            {
                                "download_url": f"/download/{Path(f['path']).name}",
                                "download_name": f["downloadName"],
                            }
                        )
                self.wfile.write(
                    f"\n---DOWNLOAD-INFO---\n{json.dumps(download_info)}".encode(
                        "utf-8"
                    )
                )

        except (json.JSONDecodeError, KeyError) as e:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            self.wfile.write(f"Invalid JSON or missing key: {e}".encode("utf-8"))
        except Exception as e:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(f"An error occurred: {e}".encode("utf-8"))

    def download_file(self):
        try:
            file_name = self.path.split("/")[-1]
            file_path = TEMP_DIR / file_name

            if file_path.is_file():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header(
                    "Content-Disposition", "attachment"
                )
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
