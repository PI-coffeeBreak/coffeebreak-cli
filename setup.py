"""Setup configuration for CoffeeBreak CLI."""

import os
import sys

from setuptools import find_packages, setup

# Get version from package
here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(here, "coffeebreak"))
try:
    from coffeebreak import __author__, __version__
except ImportError:
    __version__ = "0.1.0"
    __author__ = "CoffeeBreak Team"

# Get the long description from the README file
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="coffeebreak-cli",
    version=__version__,
    description="CoffeeBreak development and deployment automation tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=__author__,
    author_email="coffeebreak@aettua.pt",
    keywords="development deployment automation cli",
    packages=find_packages(),
    python_requires=">=3.8",
    data_files=[
        ("man/man1", ["man/man1/coffeebreak.1"]),
        (
            "man/man5",
            ["man/man5/coffeebreak.yml.5", "man/man5/coffeebreak-plugin.yml.5"],
        ),
    ],
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "docker>=6.0.0",
        "gitpython>=3.1.0",
        "jinja2>=3.0.0",
        "cryptography>=3.4.0",
        "jsonschema>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.12.0",
            "mypy>=0.991",
        ],
    },
    entry_points={
        "console_scripts": [
            "coffeebreak=coffeebreak.cli:cli",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/PI-coffeeBreak/coffeebreak-cli/issues",
        "Source": "https://github.com/PI-coffeeBreak/coffeebreak-cli",
    },
)
