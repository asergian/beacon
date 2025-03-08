"""Alembic environment configuration for database migrations.

This module configures the migration environment for Alembic to handle
database schema migrations using Flask-Migrate and SQLAlchemy.
It provides functions for running migrations in both online and offline modes,
and utilities for accessing the database engine and metadata.

The module is executed by Alembic during migration commands and should not
be run directly.
"""

import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    """Get the SQLAlchemy engine from the current Flask application.
    
    This function attempts to access the database engine using different methods
    to support both older and newer versions of Flask-SQLAlchemy.
    
    Returns:
        SQLAlchemy.Engine: The database engine from the current Flask application.
        
    Raises:
        TypeError, AttributeError: If the engine cannot be accessed due to 
            compatibility issues or configuration problems.
    """
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    """Get the database URL from the SQLAlchemy engine.
    
    This function extracts the connection URL from the engine and formats it
    for use with Alembic configuration, handling differences in SQLAlchemy versions.
    
    Returns:
        str: The database connection URL, with percent signs escaped.
        
    Raises:
        AttributeError: If the URL cannot be extracted from the engine.
    """
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    """Get the SQLAlchemy metadata from the Flask application.
    
    This function retrieves the metadata object which contains database schema
    information, supporting both newer and older versions of SQLAlchemy.
    
    Returns:
        SQLAlchemy.MetaData: The metadata object containing database schema information.
    """
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    
    Returns:
        None
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    
    This is the preferred method for running migrations as it allows
    for actual database connections and more complex migration operations.
    
    Returns:
        None
    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        """Process revision directives to prevent empty migrations.
        
        This callback checks if the migration would be empty and prevents
        the creation of an unnecessary migration file.
        
        Args:
            context: The migration context.
            revision: The revision being processed.
            directives: List of revision directives.
            
        Returns:
            None
        """
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
