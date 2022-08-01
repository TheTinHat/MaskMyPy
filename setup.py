from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="maskmypy",
    version="0.0.8",
    author="David Swanlund",
    author_email="david.swanlund@gmail.com",
    description="Geographic masking tools for spatial data anonymization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    install_requires=[
        "osmnx>=1.2.0",
        "geopandas>=0.10",
        "scikit-learn>=1.1.1",
    ],
    python_requires=">=3.8",
    # entry_points={
    #     "console_scripts": ["maskmypy=maskmypy.command_line:cli"],
    # },
)
