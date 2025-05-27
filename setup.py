from setuptools import setup, find_packages

setup(
    name="vegan2d",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'flask==2.3.3',
        'python-dotenv==1.0.0',
        'gunicorn==21.2.0',
        'supabase==1.0.3',
    ],
    python_requires='>=3.7',
)
