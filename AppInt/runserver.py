"""
This script runs the AppInt application using a development server.
"""
from flask import Flask
from click import echo

app = Flask(__name__)

try:
    from .AppInt.ldap import ldap_blueprint
    app.register_blueprint(ldap_blueprint)
except ModuleNotFoundError:
    echo('Module at path .\\AppInt\\ldap.py is not found!')

if __name__ == '__main__':
    app.run()
