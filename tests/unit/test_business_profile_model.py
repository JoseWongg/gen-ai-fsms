from sqlalchemy import String

from gen_ai_fsms.db.models.business_profile import (
    BusinessProfile,
)


def test_business_profile_defines_fsms_responsible_person_fields():
    table = BusinessProfile.__table__

    user_id_column = (
        table.c.fsms_responsible_person_user_id
    )
    name_column = (
        table.c.fsms_responsible_person_name
    )

    assert user_id_column.nullable is True
    assert user_id_column.index is True

    foreign_keys = list(user_id_column.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"
    assert foreign_keys[0].ondelete == "SET NULL"

    assert name_column.nullable is True
    assert isinstance(name_column.type, String)
    assert name_column.type.length == 255
