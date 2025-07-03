from setuptools import setup, find_packages

setup(
    name="lcmware",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "lcm",
    ],
    python_requires=">=3.6",
    description="lcmware - LCM-based RPC framework for services and actions",
    author="Your Name",
    license="MIT",
)