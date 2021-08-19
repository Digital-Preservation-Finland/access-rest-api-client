from setuptools import setup


setup(
    name='dpres-access-rest-api-client',
    packages=["dpres_access_rest_api_client"],
    package_dir={
        "dpres_access_rest_api_client": "dpres_access_rest_api_client"
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "click",
        "requests",
        "humanize",
        "tabulate"
    ],
    entry_points={
        "console_scripts": [
            "access-client = dpres_access_rest_api_client.cli:main"
        ]
    },
    python_requires=">=3.6",
    use_scm_version=True
)
