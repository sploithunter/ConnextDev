# Dockerfile for isolated DDS benchmark execution
# Build: docker build -t dds-benchmark .
# Run: docker run --rm -v $(pwd):/benchmark dds-benchmark python /benchmark/run_all_benchmarks.py --quick

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install RTI Connext DDS (you'll need to provide the installer)
# COPY rti_connext_dds-*.run /tmp/
# RUN chmod +x /tmp/rti_connext_dds-*.run && /tmp/rti_connext_dds-*.run --mode unattended

# Set NDDSHOME (adjust path as needed)
ENV NDDSHOME=/opt/rti/rti_connext_dds-7.3.0
ENV PATH=$NDDSHOME/bin:$PATH
ENV LD_LIBRARY_PATH=$NDDSHOME/lib/x64Linux4gcc7.3.0:$LD_LIBRARY_PATH

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install aider
RUN pip install --no-cache-dir aider-chat

# Working directory
WORKDIR /benchmark

# Default command
CMD ["python", "run_all_benchmarks.py", "--help"]

