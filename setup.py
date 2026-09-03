"""
Setup file for the petsseries package
"""

from setuptools import setup

setup(
    name="petsseries",
    version="1.1.0",
    description="A Unofficial Python client for interacting with the Philips Pets Series API",
    author="AboveColin",
    author_email="colin@cdevries.dev",
    packages=["petsseries"],
    license="MIT",
    extras_require={
        "test": ["pytest>=8", "pytest-asyncio>=1.0", "pytest-cov"],
    },
    install_requires=[
        "aiohttp",
        "aiofiles",
        "certifi",
        "PyJWT",
        "tinytuya",
        "cryptography",
        "tuya-mobile>=1.0.0",
    ],
    python_requires=">=3.11",
    url="https://github.com/abovecolin/petsseries",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    long_description_content_type="text/markdown",
    long_description=open("README.md", encoding="utf-8").read(),
)
