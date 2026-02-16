import os
import yaml


current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
env_file_path = os.path.join(root_dir, 'env', 'config.yaml')
secrets_path = os.path.join(root_dir, 'credentials', 'env_secrets.yaml')


try:
    with open(env_file_path, 'r') as file:
        env_vars = yaml.safe_load(file)['env_var']

    for key, value in env_vars.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    print(f"Config file not found at {env_file_path}, skipping...")

env = os.environ.get('env')
assert env is not None, 'A value for env should be set in environment variables'


try:
    with open(secrets_path, 'r') as file:
        secrets_var = yaml.safe_load(file)[f'{env}-workers-secrets']

    for key, value in secrets_var.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    print(f"Secrets file not found at {secrets_path}, skipping...")