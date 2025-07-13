# Import all the models, so that TimestampedBase has them before being imported by Alembic

from db.base_class import TimestampedBase as Base  # noqa: F401
from db.tables.blog_post import BlogPost  # noqa: F401
from db.tables.user import User # noqa: F401
from db.tables.membership import Membership # noqa: F401
from db.tables.vacancy import Vacancy # noqa: F401
from db.tables.application import Application # noqa: F401
from db.tables.placement import Placement # noqa: F401
from db.tables.message import Message # noqa: F401
