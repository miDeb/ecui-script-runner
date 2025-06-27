import json
import os
import unittest
import requests
import subprocess
import time
import tempfile
import shutil
from pathlib import Path


class TestScriptRunner(unittest.TestCase):
    def setUp(self):
        self.server_process = subprocess.Popen(["python", "-u", "server.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Give the server a moment to start up
        time.sleep(0.1)

    def tearDown(self):
        self.server_process.terminate()
        self.server_process.wait(timeout=5)  # Wait for the process to terminate

        self.server_process.stdout.close()
        self.server_process.stderr.close()

    def test_execute_simple_command(self):
        script_config = {
            "id": "test-1",
            "title": "Simple Echo",
            "command": "echo",
            "args": ["Hello", "World"],
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello World", response.text)

    def test_execute_with_temp_file(self):
        script_config = {
            "id": "test-2",
            "title": "Temp File Test",
            "command": "bash",
            "args": [
                "-c",
                'echo "This is a test" > "$0"',
                {"type": "tmp-file-path", "download": True, "downloadName": "test.txt"},
            ],
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 200)
        self.assertIn("---DOWNLOAD-INFO---", response.text)
        download_info = json.loads(response.text.split("---DOWNLOAD-INFO---")[1])
        self.assertIn("download_url", download_info["temp_files"][0])
        self.assertEqual(download_info["temp_files"][0]["download_name"], "test.txt")

        # Test downloading the file
        download_url = download_info["temp_files"][0]["download_url"]
        download_response = requests.get(f"http://localhost:8000{download_url}")
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.text, "This is a test\n")

    def test_invalid_command(self):
        script_config = {
            "id": "test-3",
            "title": "Invalid Command",
            "command": "nonexistentcommand",
            "args": [],
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Command not found: nonexistentcommand", response.text)

    def test_no_download_on_failed_command(self):
        script_config = {
            "id": "test-5",
            "title": "Failing command with temp file",
            "command": "bash",
            "args": [
                "-c",
                'echo "This should not be downloaded" > "$1"; exit 1',
                {
                    "type": "tmp-file-path",
                    "download": True,
                    "downloadName": "should_not_download.txt",
                },
            ],
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("---DOWNLOAD-INFO---", response.text)

    def test_invalid_json(self):
        response = requests.post(
            "http://localhost:8000/execute",
            data="{invalid json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)

    def test_execute_python_c_command(self):
        script_config = {
            "id": "my-script-1",
            "title": "Run a simple Python script",
            "command": "python",
            "args": [
                "-c",
                "import sys; print('Hello from Python'); print('Args:', sys.argv[1:]); f=open(sys.argv[1],'w'); f.write('Temporary file content'); f.close();",
                {
                    "type": "tmp-file-path",
                    "download": True,
                    "downloadName": "output.txt"
                }
            ]
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello from Python", response.text)
        self.assertIn("Args:", response.text)
        self.assertIn("---DOWNLOAD-INFO---", response.text)

        download_info = json.loads(response.text.split("---DOWNLOAD-INFO---")[1])
        self.assertIn("download_url", download_info["temp_files"][0])
        self.assertEqual(download_info["temp_files"][0]["download_name"], "output.txt")

        # Test downloading the file
        download_url = download_info["temp_files"][0]["download_url"]
        download_response = requests.get(f"http://localhost:8000{download_url}")
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.text, "Temporary file content")


class TestCustomScriptExecution(unittest.TestCase):
    def setUp(self):
        self.config_dir = tempfile.mkdtemp()
        self.scripts_dir = Path(self.config_dir) / "scripts"
        self.scripts_dir.mkdir()

        self.test_script_path = self.scripts_dir / "test_script.sh"
        with open(self.test_script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Hello from custom script'")
        os.chmod(self.test_script_path, 0o755)

        env = os.environ.copy()
        env["ECUI_CONFIG_PATH"] = self.config_dir

        self.server_process = subprocess.Popen(
            ["python", "-u", "server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        time.sleep(0.1)

    def tearDown(self):
        self.server_process.terminate()
        self.server_process.wait(timeout=5)
        self.server_process.stdout.close()
        self.server_process.stderr.close()
        shutil.rmtree(self.config_dir)

    def test_execute_custom_script(self):
        script_config = {
            "id": "custom-script-test",
            "title": "Custom Script Test",
            "command": "test_script.sh",
            "args": [],
        }
        response = requests.post("http://localhost:8000/execute", json=script_config)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello from custom script", response.text)


if __name__ == "__main__":
    unittest.main()