# coding: utf-8
from setuptools import setup, find_packages

setup(
    name='celery_progress_bar',
    packages=find_packages(),
    description='extension for django/celery',
    url='https://github.com/ShmakovVA/celery_progress_bar',
    author='Vadim Shmakov',
    install_requires=[
        'django >=1.7, <1.12',
        'celery>=3.1.10, <=3.1.14',
        'django-environ >=0.4.5, <0.5',
    ],
    include_package_data=True,
    package_data={
        'celery_progress_bar': ['templates/*.*'],
    },
)
