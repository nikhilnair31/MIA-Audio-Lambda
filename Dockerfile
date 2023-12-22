FROM public.ecr.aws/lambda/python:3.11

RUN /var/lang/bin/python3.11 -m pip install --upgrade pip

# Install git if not already present
RUN yum install -y git

# Install system updates and dependencies
RUN yum update -y && yum install -y tar gzip

# Compile and install the desired version of sqlite3
RUN curl -O https://www.sqlite.org/2023/sqlite-autoconf-3390000.tar.gz && \
    tar xzf sqlite-autoconf-3390000.tar.gz && \
    cd sqlite-autoconf-3390000 && \ 
    ./configure --prefix=/usr && \
    make && \
    make install

# Check sqlite3 version
RUN sqlite3 --version

# Copy function code
COPY requirements.txt .
RUN pip install -r requirements.txt

# COPY lambda_function.py .
COPY lambda_function.py .

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "lambda_function.handler" ]