FROM python:3.9

WORKDIR /home/admin/mcscale

# Install system packages
RUN apt-get update && apt-get install -y iputils-ping

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (cached by Docker layer if unchanged)
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

CMD ["python", "-u", "main.py"]

# docker build --tag mcscale:1.0v .
# docker tag mcscale:1.0v mochigome/mcscale:1.0v
# docker push mochigome/mcscale:1.0v