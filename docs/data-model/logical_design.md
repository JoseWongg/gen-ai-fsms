# Logical Database Design – FSMS Onboarding System (v1)

## Tables and Columns

### BusinessProfile

- `id` – INTEGER, PRIMARY KEY, AUTO_INCREMENT. Unique identifier.
- `business_name` – VARCHAR(255), NOT NULL. Name of the restaurant.
- `site_name` – VARCHAR(255), NULLABLE. Optional site/location name.
- `created_at` – DATETIME, NOT NULL, DEFAULT CURRENT_TIMESTAMP. When the profile was created.
- `updated_at` – DATETIME, NULLABLE, ON UPDATE CURRENT_TIMESTAMP. Last update.
- `status` – VARCHAR(50), DEFAULT 'active'. Values: active / archived.

### Condition

- `id` – INTEGER, PRIMARY KEY, AUTO_INCREMENT. Unique identifier.
- `condition_id` – VARCHAR(50), UNIQUE, NOT NULL. Ontology key (e.g., `chills_food`).
- `condition_name` – VARCHAR(100), NOT NULL. Human‑readable name.
- `description` – TEXT, NULLABLE. Explanation of the condition.
- `parent_condition_id` – VARCHAR(50), NULLABLE. For hierarchical conditions (unused in v1).
- `status` – VARCHAR(20), DEFAULT 'active'. Values: active / deprecated.

### ConditionValue

- `id` – INTEGER, PRIMARY KEY, AUTO_INCREMENT. Unique identifier.
- `business_profile_id` – INTEGER, FOREIGN KEY (BusinessProfile.id), NOT NULL. Which restaurant.
- `condition_id` – VARCHAR(50), NOT NULL, INDEXED. References `Condition.condition_id`.
- `value` – VARCHAR(20), NOT NULL. Values: true / false / unknown / not_asked.
- `source` – VARCHAR(50), DEFAULT 'user_answer'. Values: user_answer / admin_set / imported.
- `answered_at` – DATETIME, DEFAULT CURRENT_TIMESTAMP. When the value was last set.
- `last_updated_at` – DATETIME, NULLABLE, ON UPDATE CURRENT_TIMESTAMP. Last change.
- `notes` – TEXT, NULLABLE. Free‑text notes (e.g., context of answer).

### ApprovedSafetyPoint

- `id` – INTEGER, PRIMARY KEY, AUTO_INCREMENT. Unique identifier.
- `business_profile_id` – INTEGER, FOREIGN KEY (BusinessProfile.id), NOT NULL. Which restaurant.
- `safety_point_id` – VARCHAR(50), NOT NULL, INDEXED. Example: "4.1.1.1".
- `safe_method_id` – VARCHAR(50), NOT NULL. Example: "4.1".
- `safe_method_name` – VARCHAR(255), NOT NULL. Copy of the safe method name (for display).
- `safety_point_text` – TEXT, NOT NULL. Copy of the safety point text (for display).
- `approved_by_user_id` – INTEGER, NOT NULL. References `users.id` (must be admin).
- `approved_at` – DATETIME, DEFAULT CURRENT_TIMESTAMP. When the approval was recorded.

## Indexes

- `ConditionValue(condition_id)` – for fast lookups by condition.
- `ApprovedSafetyPoint(safety_point_id)` – for filtering approved points.

## Foreign Key Constraints

- `ConditionValue.business_profile_id` → `BusinessProfile.id`
- `ApprovedSafetyPoint.business_profile_id` → `BusinessProfile.id`
- `ApprovedSafetyPoint.approved_by_user_id` → `users.id`

## Notes

- The attribute `approved_by_user_id` references the `users` table (from system authentication).
- No cascade deletes are defined in v1 (business profiles are never deleted).
- The `condition_id` in `ConditionValue` is a string (the ontology key), not a numeric foreign key, to simplify seeding and avoid circular dependencies.
- The compiled SFBB content is not stored in the database; it is loaded from a JSON file.
