# coding=utf-8
from __future__ import print_function, unicode_literals

# UTF-8 stderr: http://stackoverflow.com/a/2001767/141395
import codecs
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
sys.stderr = codecs.getwriter('utf-8')(sys.stderr)

import os

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
from flask_sslify import SSLify
from bugsnag.flask import handle_exceptions
from bugsnag.celery import connect_failure_handler
from flask_sqlalchemy import SQLAlchemy
from celery import Celery


db = SQLAlchemy()
celery = Celery()


def expand_config(name=None):
    if not name:
        name = "default"
    return "openedx_webhooks.config.{classname}Config".format(
        classname=name.capitalize(),
    )


def create_app(config=None):
    app = Flask(__name__)
    handle_exceptions(app)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    config = config or os.environ.get("OPENEDX_WEBHOOKS_CONFIG") or "default"
    app.config.from_object(expand_config(config))

    db.init_app(app)
    create_celery_app(app)
    if not app.debug:
        SSLify(app)

    # attach Flask-Dance blueprints
    from .oauth import jira_bp as jira_oauth_bp
    app.register_blueprint(jira_oauth_bp, url_prefix="/login")
    from .oauth import github_bp as github_oauth_bp
    app.register_blueprint(github_oauth_bp, url_prefix="/login")

    # attach our blueprints
    from .github_views import github_bp
    app.register_blueprint(github_bp, url_prefix="/github")
    from .jira_views import jira_bp
    app.register_blueprint(jira_bp, url_prefix="/jira")
    from .ui import ui as ui_blueprint
    app.register_blueprint(ui_blueprint)

    return app


def create_celery_app(app=None, config="worker"):
    """
    adapted from http://flask.pocoo.org/docs/0.10/patterns/celery/
    """
    app = app or create_app(config=config)
    celery.main = app.import_name
    celery.conf["BROKER_URL"] = app.config["CELERY_BROKER_URL"]
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    connect_failure_handler()
    return celery
