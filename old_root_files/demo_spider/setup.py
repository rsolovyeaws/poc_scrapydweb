from setuptools import setup, find_packages

setup(
    name='demo',
    version='1.0',
    packages=find_packages(),
    entry_points={'scrapy': ['settings = demo.settings']},
    install_requires=[
        'scrapy>=2.12.0',
        'selenium>=4.13.0',
    ],
)