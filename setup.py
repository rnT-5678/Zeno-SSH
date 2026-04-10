from setuptools import setup, find_packages

setup(
    name='ssh-admin',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.1.7',
        'fabric>=3.2.2',
        'colorama>=0.4.6',
        'PyGObject>=3.42.0',
    ],
    entry_points={
        'console_scripts': [
            'ssh-admin = src.ssh_admin:cli',
        ],
    },
)
