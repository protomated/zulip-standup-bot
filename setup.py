#!/usr/bin/env python3
"""
Setup script for Zulip Standup Bot
"""

from setuptools import setup, find_packages
import os

# Read README for long description
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
try:
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "Zulip Standup Bot - Automated team standups for Zulip"

# Read requirements
requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
try:
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith('#') and not line.startswith('-')
        ]
except FileNotFoundError:
    requirements = [
        'zulip>=0.8.0',
        'zulip-bots>=0.8.0',
        'APScheduler==3.10.4',
        'pytz>=2023.3',
        'requests>=2.31.0',
        'psycopg2-binary>=2.9.0',
    ]

setup(
    name='zulip-standup-bot',
    version='1.0.0',
    description='Production-ready bot for automating daily team standups in Zulip',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Organization',
    author_email='contact@your-org.com',
    url='https://github.com/your-org/zulip-standup-bot',
    project_urls={
        'Bug Reports': 'https://github.com/your-org/zulip-standup-bot/issues',
        'Source': 'https://github.com/your-org/zulip-standup-bot',
        'Documentation': 'https://github.com/your-org/zulip-standup-bot/wiki',
    },
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'black>=23.0.0',
            'isort>=5.12.0',
            'mypy>=1.5.0',
            'flake8>=6.0.0',
        ],
        'ai': [
            'openai>=1.0.0',
            'groq>=0.4.0',
        ],
        'postgresql': [
            'psycopg2-binary>=2.9.0',
        ]
    },
    entry_points={
        'console_scripts': [
            'zulip-standup-bot=run_standup_bot:main',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Communications :: Chat',
        'Topic :: Office/Business',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='zulip bot standup scrum team automation chat',
    zip_safe=False,
)
