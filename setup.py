from setuptools import setup, find_packages

setup(
    name="vegan2d",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'flask==2.3.3',
        'supabase==1.0.3',
        'python-dotenv==1.0.0',
        'gunicorn==21.2.0',
        'httpx>=0.24.0,<0.25.0',
        'postgrest-py>=0.10.0,<0.11.0',
        'gotrue>=2.1.0,<3.0.0',
    ],
)
