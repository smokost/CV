try:
    import sqlalchemy
except ImportError as err:
    raise RuntimeError(
        'SQLAlchemy is not installed. Install sqlalchemy or run `pip install cc-clean-arch[sql]`.'
    ) from err
