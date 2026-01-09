import argparse
import json
import os
import logging
import subprocess
import sys
import typing

import boto3
from botocore.exceptions import ClientError

from soongo_data.utils.logging_utils import gen_logger

# AWS Configuration
ENV_DICT = {
    "staging": {
        "AWS_REGION": "eu-west-3",
        "ACCOUNT_ID": "443370677666",
        "LAMBDA_ROLE_ARN": "arn:aws:iam::443370677666:role/lambda_soongo-staging-data_secrets-manager",
        "subnets": [
            'subnet-0faa65b242d5e3d7c',
        ],
        "security_groups": [
            'sg-03ddc03be608cb999',
        ],
        "DATA_S3_BUCKET": "soongo-staging-data",
    },
    "prod": {
        "AWS_REGION": "eu-west-3",
        "ACCOUNT_ID": "418272762572",
        "LAMBDA_ROLE_ARN": "arn:aws:iam::418272762572:role/service-role/synchronise_connector-role-f717oaby",
        "subnets": [
            'subnet-09782665aa68c56bd',
        ],
        "security_groups": [
            'sg-00b6b863a8b218a0b',
        ],
        "DATA_S3_BUCKET": "soongo-production",
    }
}
DOCKER_IMAGE_TAG = "latest"  # Replace with your Docker image tag


def build_docker_image(
    logger: logging.Logger,
    lambda_name: str,
) -> None:
    """
    Build the Docker image for the Lambda function.
    """
    build_dir = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )
    docker_path = os.path.join(
        build_dir,
        f"infrastructure/lambdas/{lambda_name}/Dockerfile",
    )
    logger.info(
        '%s',
        ' '.join([
            "docker",
            "build",
            "-t",
            f"{lambda_name}:{DOCKER_IMAGE_TAG}",
            "-f",
            docker_path,
            build_dir,
        ])
    )
    try:
        logger.info(f"Building Docker image for Lambda '{lambda_name}'...")
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                f"{lambda_name}:{DOCKER_IMAGE_TAG}",
                "-f",
                docker_path,
                build_dir,
            ],
            check=True,
        )
        logger.info("Docker image built successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error building Docker image: {e}", exc_info=True)
        sys.exit(1)


def push_docker_image_to_ecr(
    ecr_client: boto3.client,
    logger: logging.Logger,
    aws_account_id: str,
    aws_region: str,
    lambda_name: str,
    lambda_role_arn: str,
) -> str:
    """
    Push the Docker image to Amazon ECR.
    """
    try:
        # Authenticate Docker to ECR
        logger.info("Authenticating Docker to ECR...")
        auth_token = ecr_client.get_authorization_token()
        ecr_url = auth_token["authorizationData"][0]["proxyEndpoint"]
        aws_command = ["aws", "ecr", "get-login-password", "--region", aws_region]
        docker_command = ["docker", "login", "--username", "AWS", "--password-stdin", ecr_url]
        aws_process = subprocess.Popen(aws_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(
            docker_command,
            stdin=aws_process.stdout,  # Pipe the output of the AWS command to Docker
            check=True,
        )
        aws_process.stdout.close()

        # Create ECR repository if it doesn't exist
        ecr_repository_name = f'lambdas/{lambda_name}'
        try:
            ecr_client.describe_repositories(repositoryNames=[ecr_repository_name])
            logger.debug(f"ECR repository '{ecr_repository_name}' already exists.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                logger.info(f"Creating ECR repository '{ecr_repository_name}'...")
                create_repository_with_lambda_access(
                    ecr_client=ecr_client,
                    repository_name=ecr_repository_name,
                    logger=logger,
                    account_id=aws_account_id,
                    lambda_role_arn=lambda_role_arn,
                )
            else:
                raise

        # Tag and push the Docker image
        ecr_image_uri = f"{aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com/{ecr_repository_name}:{DOCKER_IMAGE_TAG}"
        logger.info(f"Tagging Docker image as '{ecr_image_uri}'...")
        subprocess.run(["docker", "tag", f"{lambda_name}:{DOCKER_IMAGE_TAG}", ecr_image_uri], check=True)

        logger.info(f"Pushing Docker image to ECR: {ecr_image_uri}...")
        subprocess.run(["docker", "push", ecr_image_uri], check=True)

        logger.info("Docker image pushed successfully.")
        return ecr_image_uri

    except Exception as e:
        logger.error(f"Error during Docker/ECR operations: {e}", exc_info=True)
        sys.exit(1)


def create_or_update_lambda(
    ecr_image_uri: str,
    lambda_client: boto3.client,
    lambda_name: str,
    lambda_role_arn: str,
    logger: logging.Logger,
    vpc_subnets: typing.List[str],
    vpc_security_groups: typing.List[str],
    env: str,
    data_s3_bucket: str,
):
    """
    Create a new Lambda function or update its code if it already exists.
    """
    try:
        # Check if the Lambda function exists
        try:
            function = lambda_client.get_function(FunctionName=lambda_name)
            function_exists = True
            logger.info(f"Lambda function '{lambda_name}' already exists.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                function_exists = False
                logger.info(f"Lambda function '{lambda_name}' does not exist. Creating it...")
            else:
                raise

        # Create or update the Lambda function
        if function_exists:
            status = function['Configuration']['State']
            last_update_status = function['Configuration'].get('LastUpdateStatus')
            if status == 'Pending' or last_update_status == 'InProgress':
                logger.info(
                    "Update already in progress for Lambda %s. Skipping.",
                    lambda_name,
                )
            else:
                lambda_client.update_function_code(
                    FunctionName=lambda_name,
                    ImageUri=ecr_image_uri,
                )
                logger.info(
                    "Updating Lambda %s's  function code updated successfully.",
                    lambda_name,
                )
        else:
            lambda_client.create_function(
                FunctionName=lambda_name,
                Role=lambda_role_arn,
                Code={"ImageUri": ecr_image_uri},
                PackageType="Image",
                Publish=True,
                Timeout=900,  # 15 minutes
                MemorySize=1024,  # 1 GB
                VpcConfig={
                    'SubnetIds': vpc_subnets,
                    'SecurityGroupIds': vpc_security_groups,
                },
                Environment={
                    'Variables': {
                        'env': env,
                        'DATA_S3_BUCKET': data_s3_bucket,
                    }
                },
            )
            logger.info(
                "Successfully created Lambda %s's  function",
                lambda_name,
            )
    except ClientError as e:
        logger.error(
            "Error updating lambda %s: %s",
            lambda_name,
            e,
            exc_info=True,
        )
        sys.exit(1)


def create_repository_with_lambda_access(
    ecr_client: boto3.client,
    repository_name: str,
    logger: logging.Logger,
    lambda_role_arn: str,
    account_id: str,
):
    try:
        # Create the repository
        ecr_client.create_repository(
            repositoryName=repository_name
        )
        logger.info(f"Repository '{repository_name}' created successfully.")

        # Define the permission policy
        permission_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowLambdaECRAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:BatchCheckLayerAvailability"
                    ],
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                        "AWS": [
                            f"arn:aws:iam::{account_id}:user/backend_user",
                            lambda_role_arn,
                            f"arn:aws:iam::{account_id}:root"
                        ]
                    }
                }
            ]
        }

        # Attach the permission policy to the repository
        ecr_client.set_repository_policy(
            repositoryName=repository_name,
            policyText=json.dumps(permission_policy)
        )
        logger.info(
            "Permission policy attached to repository %s successfully.",
            repository_name
        )

    except ecr_client.exceptions.RepositoryAlreadyExistsException:
        logger.warning(
            "Repository %s already exists.",
            repository_name
        )
    except ecr_client.exceptions.ClientError as e:
        logger.error(
            "Failed to create repository or attach policy: %s",
            e,
            exc_info=True
        )
        raise


def arg_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Refactor a folder for upload into S3, respecting S3 naming conventions'
    )

    parser.add_argument(
        '-e',
        '--env',
        type=str,
        required=True,
        help='staging or prod'
    )

    args = parser.parse_args()

    if args.env not in ('staging', 'prod'):
        parser.error("The --env argument must be either 'staging' or 'prod'.")

    return args


def main():

    # Initialize args loggers and clients
    args = arg_parser()
    logger = gen_logger(__name__)
    logger.info('Starting deployment process for environment %s', args.env)
    aws_session = boto3.Session(profile_name=f'{args.env}-backend-user')
    os.environ['AWS_PROFILE'] = f'{args.env}-backend-user'

    aws_args = ENV_DICT[args.env]
    ecr_client = aws_session.client(
        "ecr",
        region_name=aws_args['AWS_REGION']
    )
    lambda_client = aws_session.client(
        "lambda",
        region_name=aws_args['AWS_REGION']
    )
    root_dir = os.path.dirname(__file__)
    lambda_dirs = [
        entry for entry in os.listdir(root_dir)
        if os.path.isdir(os.path.join(root_dir, entry))
    ]
    for lambda_name in lambda_dirs:
        build_docker_image(
            logger=logger,
            lambda_name=lambda_name,
        )
        ecr_image_uri = push_docker_image_to_ecr(
            ecr_client=ecr_client,
            logger=logger,
            aws_account_id=aws_args['ACCOUNT_ID'],
            aws_region=aws_args['AWS_REGION'],
            lambda_name=lambda_name,
            lambda_role_arn=aws_args['LAMBDA_ROLE_ARN'],
        )
        create_or_update_lambda(
            ecr_image_uri=ecr_image_uri,
            lambda_client=lambda_client,
            lambda_name=lambda_name,
            lambda_role_arn=aws_args['LAMBDA_ROLE_ARN'],
            logger=logger,
            vpc_subnets=aws_args['subnets'],
            vpc_security_groups=aws_args['security_groups'],
            env=args.env,
            data_s3_bucket=aws_args['DATA_S3_BUCKET'],
        )
        logger.info("Deployment process completed successfully.")


if __name__ == "__main__":
    main()
