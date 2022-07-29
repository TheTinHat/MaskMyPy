from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="maskmypy",
    version="0.0.7",
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
        "matplotlib>=3.5",
        "networkx>=2.8",
        "numpy>=1.21",
        "pandas>=1.4",
        "pyproj>=3.3",
        "requests>=2.27",
        "Rtree>=1.0",
        "Shapely>=1.8,<2.0",
        "scikit-learn>=1.1.1",
    ],
    python_requires=">=3.8",
)
