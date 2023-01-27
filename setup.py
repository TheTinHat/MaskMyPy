from setuptools import setup, find_packages

with open("docs/README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="maskmypy",
    version="0.0.8",
    author="David Swanlund",
    author_email="david.swanlund@gmail.com",
    description="Python tools for anonymizing geographic data.",
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
        "pointpats==2.2.0",
    ],
    extras_require={
        "develop": [
            "pytest",
            "black",
            "mkdocs-material",
            "mkdocs-roamlinks-plugin",
            "mkdocs-git-revision-date-localized-plugin",
            "mkdocstrings-python",
        ],
        "extra": ["contextily>=1.2.0", "psutil"],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": ["maskmypy=maskmypy.cli:cli"],
    },
)
