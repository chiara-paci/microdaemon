import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read()


setuptools.setup(
    name="microdaemon",
    version=version,
    author="Chiara Paci",
    author_email="chiara.paci@gmail.com",
    description="A small framework for python services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/chiara-paci/microdaemon",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 1 - Planning ",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
)
