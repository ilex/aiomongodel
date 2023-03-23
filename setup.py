"""Setup script."""
import os.path
import re
from setuptools import setup, find_packages


install_requires = ['motor>=2.0,<4.0']


tests_require = ['pytest']


def version():
    cur_dir = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(cur_dir, 'aiomongodel', '__init__.py'), 'r') as f:
        try:
            version = re.findall(
                r"^__version__ = '([^']+)'\r?$",
                f.read(), re.M)[0]
        except IndexError:
            raise RuntimeError('Could not determine version.')

        return version


long_description = '\n'.join((open('README.rst').read(),
                              open('CHANGELOG.rst').read()))


setup(
    name="aiomongodel",
    version=version(),
    description=('ODM to use with asynchronous MongoDB Motor driver.'),
    long_description=long_description,
    setup_requires=['pytest-runner'],
    install_requires=install_requires,
    tests_require=tests_require,
    packages=find_packages(exclude=['tests*']),
    author='ilex',
    author_email='ilexhostmaster@gmail.com',
    url='https://github.com/ilex/aiomongodel',
    license='MIT',
    classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: Developers',
            'Topic :: Database',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
        ]
)
