'''
This script is for development use only. It deletes today's daily shift record(s) for a given business profile ID.

This can be useful for resetting the state of daily shifts during development and testing, especially when working with the start and end shift functionality.

To use, run this in the terminal:

python scripts/dev/reset_daily_shift_by_business_profile.py

'''

from datetime import datetime
from zoneinfo import ZoneInfo

from gen_ai_fsms.db.models.daily_shift import DailyShift
from gen_ai_fsms.db.session import SessionLocal


SHIFT_TIMEZONE = ZoneInfo("Europe/London")


def get_today_shift_date():
    return datetime.now(SHIFT_TIMEZONE).date()


def ask_business_profile_id():
    raw_value = input("Enter business_profile_id: ").strip()

    if not raw_value:
        print("No business_profile_id entered. Nothing deleted.")
        return None

    try:
        return int(raw_value)
    except ValueError:
        print("business_profile_id must be a number. Nothing deleted.")
        return None


def main():
    business_profile_id = ask_business_profile_id()

    if business_profile_id is None:
        return

    shift_date = get_today_shift_date()

    db = SessionLocal()

    try:
        shifts = (
            db.query(DailyShift)
            .filter(
                DailyShift.business_profile_id == business_profile_id,
                DailyShift.shift_date == shift_date,
            )
            .all()
        )

        if not shifts:
            print(
                f"No daily shift records found for business_profile_id={business_profile_id} "
                f"and shift_date={shift_date}."
            )
            return

        print()
        print(
            f"Found {len(shifts)} daily shift record(s) for "
            f"business_profile_id={business_profile_id}, shift_date={shift_date}:"
        )

        for shift in shifts:
            print(
                f"- id={shift.id}, status={shift.status}, "
                f"started_by_user_id={shift.started_by_user_id}, "
                f"started_at={shift.started_at}, "
                f"ended_by_user_id={shift.ended_by_user_id}, "
                f"ended_at={shift.ended_at}"
            )

        print()
        confirmation = input("Type DELETE to delete these record(s): ").strip()

        if confirmation != "DELETE":
            print("Confirmation not provided. Nothing deleted.")
            return

        for shift in shifts:
            db.delete(shift)

        db.commit()
        print("Today�s daily shift record(s) deleted.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
