# Use Python 3.9 as the base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /home/admin/mcscale

# Install necessary system packages
RUN apt-get update && apt-get install -y iputils-ping

# Install required Python packages
RUN pip install --no-cache-dir pymcprotocol pyserial python-dotenv

# Copy the current directory contents into the container's working directory
COPY . /home/admin/mcscale

# Set the command to run the application
CMD ["python", "-u", "main.py"]
