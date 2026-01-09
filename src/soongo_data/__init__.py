import os

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
env_file_path = os.path.join(root_dir, 'env', 'config.yaml')
secrets_path = os.path.join(root_dir, 'credentials', 'env_secrets.yaml')

# Load the YAML file, if exists (development)
try:
    with open(env_file_path, 'r') as file:
        env_vars = yaml.safe_load(file)['env_var']

    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    pass

env = os.environ.get('env')
assert env is not None, 'A value for env should be set in environment variables'

# Load secrets yaml, if exists (development)
try:
    with open(secrets_path, 'r') as file:
        secrets_var = yaml.safe_load(file)[f'{env}-workers-secrets']

    # Set environment variables
    for key, value in secrets_var.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    pass
