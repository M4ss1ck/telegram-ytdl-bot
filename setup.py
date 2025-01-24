from setuptools import setup, find_packages

setup(
    name="telegram-ytdl-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "python-telegram-bot>=20.0",
        "python-dotenv>=0.19.0",
        "yt-dlp>=2023.3.4",
    ],
    entry_points={
        'console_scripts': [
            'telegram-ytdl-bot=src.__main__:main',
        ],
    },
)
