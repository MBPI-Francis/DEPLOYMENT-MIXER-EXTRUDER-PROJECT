from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker # <--- IMPORT THIS
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
from os import getenv

load_dotenv()


try:
    url = URL.create(
        drivername=getenv("DB_DRIVER"),
        username=getenv("DB_USER"),
        host=getenv("DB_HOST"),
        database=getenv("DB_NAME"),
        port=getenv("DB_PORT"),
        password=getenv("DB_PASSWORD")
    )

except:
    raise ValueError("Environment not valid.")

engine = create_engine(url)

# ---> ADD THIS SESSION FACTORY <---
# This factory will create new Session objects whenever called.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Your existing connection check remains the same
is_connected = None
try:
    with engine.connect() as conn:
        is_connected = True
except OperationalError as e:
    is_connected = str(e)