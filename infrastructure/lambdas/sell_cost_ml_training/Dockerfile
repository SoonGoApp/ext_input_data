# Use the AWS-provided base image for Python
FROM public.ecr.aws/lambda/python:3.12

# Set environment variables
ARG build_env
ENV env=$build_env

# Copy the function code and dependencies
COPY infrastructure/lambdas/sell_cost_ml_training/app.py ${LAMBDA_TASK_ROOT}/
COPY infrastructure/lambdas/sell_cost_ml_training/config.yaml ${LAMBDA_TASK_ROOT}/
COPY requirements_docker.txt ./
COPY src/soongo_data ${LAMBDA_TASK_ROOT}/soongo_data/
COPY credentials ${LAMBDA_TASK_ROOT}/credentials/

ENV credentials_folder=${LAMBDA_TASK_ROOT}/credentials/

# Install dependencies
RUN pip install --no-cache-dir --timeout=120 -r requirements_docker.txt -t ${LAMBDA_TASK_ROOT}/

# Set the CMD to your Lambda handler
CMD ["app.lambda_handler"]