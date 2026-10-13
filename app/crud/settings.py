from sqlalchemy.orm import Session

from app.db.models import AISettings


def get_settings(db: Session) -> AISettings:
    settings = db.get(AISettings, 1)
    if settings is None:
        settings = AISettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, **fields) -> AISettings:
    settings = get_settings(db)
    for key, value in fields.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings
