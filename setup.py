"""
Setup file for the petsseries package
"""

from setuptools import setup

setup(
    name="petsseries",
    version="0.2.5",
    description="A Unofficial Python client for interacting with the Philips Pets Series API",
    author="AboveColin",
    author_email="colin@cdevries.dev",
    packages=["petsseries"],
    install_requires=["aiohttp", "aiofiles", "certifi", "PyJWT", "tinytuya"],
    python_requires=">=3.11",
    url="https://github.com/abovecolin/petsseries",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    long_description_content_type="text/markdown",
    long_description=open("README.md", encoding="utf-8").read(),
)
