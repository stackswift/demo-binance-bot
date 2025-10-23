from setuptools import setup, find_packages

setup(
    name="demo-binance-bot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'python-binance>=1.0.19',
        'python-dotenv>=1.0.0',
        'pytest>=7.4.0',
        'requests>=2.31.0',
        'pandas>=2.1.0',
        'numpy>=1.24.0',
        'websocket-client>=1.6.4',
        'tenacity>=8.2.3',
        'structlog>=23.1.0',
    ],
)