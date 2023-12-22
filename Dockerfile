FROM public.ecr.aws/lambda/python:3.11

RUN /var/lang/bin/python3.11 -m pip install --upgrade pip

# Copy function code
COPY requirements.txt .
RUN pip install -r requirements.txt

# COPY lambda_function.py .
COPY lambda_function.py .

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "lambda_function.handler" ]