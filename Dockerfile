# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install curl
RUN apt-get update && apt-get install -y curl

# Install InfluxDB v1 CLI
RUN curl -sL https://dl.influxdata.com/influxdb/releases/influxdb_1.8.10_amd64.deb -o influxdb.deb \
    && dpkg -i influxdb.deb \
    && cp /usr/bin/influx /usr/local/bin/influx \
    && rm influxdb.deb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install numpy pandas --root-user-action=ignore

# Set the working directory in the container
ADD ./ /home/script-runner
WORKDIR /home/script-runner

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run server.py when the container launches
CMD ["python", "-u", "server.py"]
