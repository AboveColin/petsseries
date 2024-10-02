"""
Setup file for the petsseries package
"""

from setuptools import setup, find_packages

setup(
    name="petsseries",
    version="0.1.2",
    description="An Unofficial Python client for interacting with the Philips Pets Series API",
    author="AboveColin",
    author_email="colin@cdevries.dev",
    packages=find_packages(),
    install_requires=["aiohttp", "aiofiles", "certifi", "PyJWT"],
    python_requires=">=3.11",
    url="https://github.com/abovecolin/petsseries",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    long_description_content_type="text/markdown",
    long_description=open("README.md").read(),  # pylint: disable=unspecified-encoding, consider-using-with
)
