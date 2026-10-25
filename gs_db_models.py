"""
Database models.
"""

import os
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Relationship, mapped_column

# Database file: GSW_DB in .env (default gsw.db). A relative path is taken
# from the folder of this script, so it works from any working directory.
_DB_PATH = os.getenv("GSW_DB", "gsw.db")
if not os.path.isabs(_DB_PATH):
    _DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _DB_PATH)

engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)
# engine = create_engine("sqlite:///gsw.db", echo=True)


class Base(DeclarativeBase):
    """The Base"""


class TimeStampedModel(Base):
    """
    The Base extended with stuff for relational tables
    Can probably be added to Base
    """

    __abstract__ = True
    # __allow_unmapped__ = True

    # Fields
    created_at = mapped_column(DateTime, default=datetime.now(UTC))
    updated_at = mapped_column(DateTime, onupdate=datetime.now(UTC))


class FirstName(Base):
    """Class representing a gender associated with a first name"""

    __tablename__ = "first_names"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    gender: Mapped[str] = mapped_column(String(1), nullable=True)

    def __repr__(self) -> str:
        repr_string = f"<{self.__class__.__name__} id={self.id}, "
        repr_string += f"firstname={self.first_name}, gender={self.gender}>"
        return repr_string


class City(Base):
    """Class representing a city"""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=True)

    def __repr__(self) -> str:
        # full_city = self.city
        # if bool(self.country):
        #     full_city += f" ({self.country})"
        # return full_city
        return self.city + (f" ({self.country})" if self.country else "")


class Division(TimeStampedModel):
    """Class representing a division"""

    __tablename__ = "divisions"

    # Fields
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=True)
    slug: Mapped[str] = mapped_column(
        String(101), unique=True, index=True, nullable=False
    )
    export: Mapped[bool] = mapped_column(default=False)
    single_check: Mapped[bool] = mapped_column(default=False)
    remove_diacritics: Mapped[bool] = mapped_column(default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=True, default=10)
    processed: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    processed_last_run: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    uploaded_last_run: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    count_on_site: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    short_names: Mapped[bool] = mapped_column(default=False)
    last_names_capitalized: Mapped[bool] = mapped_column(default=False)
    last_names_no_diacritics: Mapped[bool] = mapped_column(default=False)
    first_names_no_diacritics: Mapped[bool] = mapped_column(default=False)

    # Relationship
    templates = Relationship(
        "Template", back_populates="division", passive_deletes=True
    )

    def __repr__(self) -> str:
        return_msg = f"<{self.__class__.__name__} id={self.id}, name={self.name}, "
        return_msg += f"slug={self.slug}, email={self.email}, "
        return_msg += f"export={self.export}, templates={len(self.templates)})>"
        return return_msg


class Template(TimeStampedModel):
    """Class representing a template for naming folders or files"""

    __tablename__ = "templates"

    # Fields
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(2), nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String(6), nullable=False)
    operation: Mapped[str] = mapped_column(String(5), nullable=False)

    # Foreign Keys
    division_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("divisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    division = Relationship("Division", back_populates="templates")

    def __repr__(self) -> str:
        return_msg = (
            f"<{self.__class__.__name__} {self.type} {['Folder','File'][self.source]} "
        )
        return_msg += f"({['R','W'][self.operation]}): {self.format}>"
        return return_msg


class DocumentChanges(TimeStampedModel):
    """Class representing the changes made to document information"""

    __abstract__ = True

    box_number_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    document_number_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    obituary_type_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    first_name_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_name_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    birth_place_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    birth_year_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    birth_month_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    birth_day_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    death_place_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    death_year_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    death_month_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    death_day_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    gender_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    face_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    review: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(DocumentChanges):
    """Class representing an obituary document"""

    __tablename__ = "documents"

    # Fields
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Post attributes
    wp_post_id: Mapped[int] = mapped_column(Integer)  # wp_post_data['id']
    wp_post_status: Mapped[str] = mapped_column(String, nullable=True, default="")
    wp_editor: Mapped[str] = mapped_column(String, nullable=True, default="")
    wp_edit_time: Mapped[int] = mapped_column(Integer, default=0)
    wp_edited_on: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    wp_reviewer: Mapped[str] = mapped_column(String, nullable=True, default="")
    wp_review_time: Mapped[int] = mapped_column(Integer, default=0)
    wp_reviewed_on: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    wp_post_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    wp_image_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    wp_post_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    wp_image_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    wp_web_image_path: Mapped[str] = mapped_column(String, nullable=True, default="")
    wp_featured_media: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    wp_priority: Mapped[int] = mapped_column(Integer, nullable=True, default=10)

    # File attributes
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    folder_name: Mapped[str] = mapped_column(String, nullable=True)
    file_name: Mapped[str] = mapped_column(String, nullable=True)
    file_base_name: Mapped[str] = mapped_column(String, nullable=True)
    new_file_name: Mapped[str] = mapped_column(String, nullable=True)

    # Document attributes
    division_id: Mapped[int] = mapped_column(Integer, nullable=True)
    division_slug: Mapped[str] = mapped_column(String, nullable=True)
    obituary_type: Mapped[str] = mapped_column(String(2), nullable=True, default="rb")
    box_number: Mapped[str] = mapped_column(String, nullable=True, default="")
    document_number: Mapped[str] = mapped_column(String, nullable=True, default="")

    # OCR attributes
    ocr_text: Mapped[str] = mapped_column(String, nullable=True, default="")
    content: Mapped[str] = mapped_column(String, nullable=True, default="")

    # Person attributes
    first_name: Mapped[str] = mapped_column(String, nullable=True, default="")
    last_name: Mapped[str] = mapped_column(String, nullable=True, default="")
    birth_place: Mapped[str] = mapped_column(String, nullable=True, default="")
    birth_year: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    birth_month: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    birth_day: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    death_place: Mapped[str] = mapped_column(String, nullable=True, default="")
    death_year: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    death_month: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    death_day: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    # Additional info
    gender: Mapped[str] = mapped_column(String(1), nullable=True, default=None)
    face: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String, nullable=True, default="")

    # Other info
    date: Mapped[str] = mapped_column(String, nullable=True, default="")
    obituary_id: Mapped[str] = mapped_column(String, nullable=True, default="")
    processing_time: Mapped[float] = mapped_column(Float, nullable=True, default=0)


Base.metadata.create_all(engine)
