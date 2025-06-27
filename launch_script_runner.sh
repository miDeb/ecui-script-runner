#!/bin/bash
set -e

CONTAINER_NAME="script-runner"

if [ -z "${ECUI_CONFIG_PATH}" ]; then
  echo "Error: ECUI_CONFIG_PATH environment variable is not set."
  echo "Please set it to the absolute path of your configuration directory."
  exit 1
fi

echo "Stopping and removing any existing container named ${CONTAINER_NAME}"
docker rm -f ${CONTAINER_NAME} 2>/dev/null || true

echo "Building the Docker image..."
docker build -t script-runner .

echo "Running the Docker container in detached mode..."
docker run -d --name ${CONTAINER_NAME} \
  -v "${ECUI_CONFIG_PATH}:/config" \
  -e ECUI_CONFIG_PATH=/config \
  --network host \
  script-runner
echo "Container ${CONTAINER_NAME} started in background."
