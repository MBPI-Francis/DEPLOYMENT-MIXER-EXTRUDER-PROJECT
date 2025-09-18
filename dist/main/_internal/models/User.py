

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    func,
    Enum,
    ForeignKey
)
from sqlalchemy.orm import relationship
from models import Base
from constants.Enums import Department, UserRole

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    password = Column(String, nullable=False)
    workstation_name = Column(String(40), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    department = Column(Enum(Department), nullable=False)


    # reverse relationship to the auth_logs
    ### NOTE: SAMPLE ###
    #############################################################
    # user = session.query(User).first()                        #
    # for log in user.auth_logs:                                #
    #     print(log.timestamp, log.status)                      #
    #############################################################
    
    auth_logs = relationship("AuthLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(username={self.username}, role={self.role.name}, dept={self.department.name})>"

class AuthLog(Base):
    __tablename__ = "auth_logs"
    
    log_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True)
    username = Column(String(50))  # kept in case user is deleted
    event_type = Column(String(50))  # LOGIN, AUTH_ATTEMPT, LOGOUT, etc.
    status = Column(String(10))     # SUCCESS, FAIL
    additional_info = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # reverse relationship to the User
    ### NOTE: SAMPLE ###
    #############################################################
    # log = session.query(AuthLog).first()                      #
    # print(log.user.username)                                  #
    #############################################################

    user = relationship("User", back_populates="auth_logs")

    def __repr__(self):
        return f"<AuthLog(user={self.username}, type={self.event_type}, status={self.status}, time={self.timestamp})>"