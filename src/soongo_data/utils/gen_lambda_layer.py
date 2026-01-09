import argparse
import os
import re
import shutil
import subprocess
import sys
import typing
import zipfile


def main(
    output_path: str,
    requirements_file: typing.Optional[str] = None,
) -> None:
    """Create a lambda layer zip file containing all Python libraries in the
    running environment as well as the current project.

    :param output_path: path where the lambda layer is to be saved
    :param requirements_file: path to a requirements file. If not provided,
    current environnement is used.

    :returns None: but saves a zip file at the provided output_path
    """

    # Create virtual environment
    venv_dir = os.path.join(
        os.path.dirname(output_path),
        'venv',
    )
    create_venv(venv_dir)

    # Install dependencies
    install_dependencies(venv_dir, requirements_file)

    # Create layer structure
    layer_dir = os.path.join(
        os.path.dirname(output_path),
        'layer',
    )
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    create_layer_structure(
        layer_dir=layer_dir,
        venv_dir=venv_dir,
        project_dir=project_path,
    )

    # Create ZIP file
    create_zip_file(layer_dir, output_path)

    # Clean up
    shutil.rmtree(venv_dir)
    shutil.rmtree(layer_dir)


def create_venv(venv_dir: str):
    if not os.path.isdir(venv_dir):
        try:
            os.mkdir(venv_dir)
        except Exception as exc:
            raise FileNotFoundError(
                'Passed virtual environment directory does not exists'
                ' nor its parent directory'
            ) from exc

    subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True)


def install_dependencies(
    venv_dir: str,
    requirements_file: typing.Optional[str] = None,
):
    """Install required dependencies to a virtual environment so that they can
    be copied into the layer zip file

    :param venv_dir: str path to the venv directory
    :param requirements_file: optional str path to the requirements file.
        if not provided all packages of the running virtual environment
        are copied into the venv.
    """
    if not requirements_file:
        requirements_file = os.path.join(venv_dir, 'requirements_lambda.txt')
        # Open the output file in write mode
        with open(requirements_file, 'w') as file:
            # Run the command and write the output to the file
            subprocess.run(['pip', 'freeze'], stdout=file, check=True)

    clean_dependencies(requirements_file)
    subprocess.run(
        [
            os.path.join(
                venv_dir,
                'bin/pip',
            ),
            'install',
            '-r',
            requirements_file,
        ],
        check=True,
    )
    clean_venv_dir(venv_dir)


def clean_venv_dir(venv_dir: str) -> None:
    """Clean up the virtual environment directory by removing
    unnecessary files.  :param venv_dir: str path to the virtual
    environment directory
    """
    for root, _dirs, files in os.walk(venv_dir):
        for file in files:
            if file.endswith('.pyc') or file.endswith('.pyo'):
                os.remove(os.path.join(root, file))
        # Remove empty directories
        if not os.listdir(root):
            os.rmdir(root)

    # Remove the __pycache__ directories
    for root, dirs, _ in os.walk(venv_dir):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                shutil.rmtree(os.path.join(root, dir_name), ignore_errors=True)

    # Remove pip and setuptools, not necessary for the layer,
    # and botocore, included by AWS
    for pkg in ('setuptools', 'pip', 'botocore'):
        pkg_dir = os.path.join(venv_dir, 'lib/python3.12/site-packages', pkg)
        if os.path.isdir(pkg_dir):
            shutil.rmtree(
                pkg_dir,
                ignore_errors=True,
            )


def clean_dependencies(
    requirements_file: str, drop_lst: typing.Tuple[str] = (r'^install==',)
) -> None:
    with open(requirements_file, 'r') as file:
        filtered_lines = [
            line
            for line in file.readlines()
            if not any(
                re.match(pattern, line, flags=re.IGNORECASE)
                for pattern in drop_lst
            )
        ]

    with open(requirements_file, 'w') as file:
        file.writelines(filtered_lines)


def create_layer_structure(
    layer_dir: str,
    venv_dir: str,
    project_dir: str,
    python_version: str = '3.12',
):
    site_packages_dir = os.path.join(
        layer_dir,
        'python',
        'lib',
        f'python{python_version}',
        'site-packages',
    )
    os.makedirs(site_packages_dir, exist_ok=True)

    # Copy project code into the layer directory
    project_name = os.path.basename(project_dir)
    shutil.copytree(project_dir, os.path.join(site_packages_dir, project_name))

    # Copy installed dependencies into the layer directory
    venv_site_packages_dir = os.path.join(
        venv_dir,
        'lib',
        f'python{python_version}',
        'site-packages',
    )
    for root, _dirs, files in os.walk(venv_site_packages_dir):
        for file in files:
            src_file = os.path.join(
                root,
                file,
            )
            dst_file = os.path.join(
                site_packages_dir,
                os.path.relpath(
                    src_file,
                    venv_site_packages_dir,
                ),
            )
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            shutil.copy2(src_file, dst_file)


def create_zip_file(
    layer_dir: str,
    output_path: str,
):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _dirs, files in os.walk(layer_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, layer_dir)
                zipf.write(file_path, arcname)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Process some files.')

    # Adding the -o/--output-file argument
    parser.add_argument(
        '-o',
        '--output-file',
        type=str,
        required=True,
        help='The path to the output zip file. Must end in .zip',
    )

    # Adding the -r/--requirement-file argument (optional)
    parser.add_argument(
        '-r',
        '--requirement-file',
        type=str,
        required=False,
        default=None,
        help='The requirement file path (optional)',
    )

    args = parser.parse_args()
    args.output_file = os.path.expanduser(args.output_file)
    if args.requirement_file:
        args.requirement_file = os.path.expanduser(args.requirement_file)

    if not os.path.isdir(os.path.dirname(args.output_file)):
        raise FileNotFoundError(
            'The provided output path points to a non existing folder: ',
            args.output_file,
        )

    if args.requirement_file and not os.path.isfile(args.requirement_file):
        raise FileNotFoundError(
            'The provided requirement_file path is not a valid file: ',
            args.output_file,
        )

    if not args.output_file.endswith('.zip'):
        raise ValueError('Provided output_file path must end up in .zip')

    return args


if __name__ == '__main__':
    args = parse_args()

    main(args.output_file, args.requirement_file)
