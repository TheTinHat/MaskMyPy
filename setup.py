from setuptools import find_packages, setup

with open("docs/README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="maskmypy",
    version="1.1.0",
    author="David Swanlund",
    author_email="maskmypy@swanlund.dev",
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
        "osmnx>=1.7.0,<2.0",
        "scikit-learn>=1.1.1,<2.0",
        "pointpats>=2.3.0,<3.0",
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
        "extra": ["contextily>=1.2.0"],
    },
    python_requires=">=3.10",
)
