from setuptools import setup, find_packages

setup(
    name='demo',  # must match the project name in scrapy.cfg
    version='0.1',
    packages=find_packages(),
    entry_points={'scrapy': ['settings = demo.settings']},
)
