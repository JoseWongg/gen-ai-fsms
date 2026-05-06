# Conceptual Database Design – FSMS Onboarding System (v1)

## Overview

The database supports the core functionality of the onboarding system:

- **Business Profile** – represents a food business that is using the system.
- **Condition Ontology** – a set of boolean‑like flags (true/false/unknown/not_asked) that describe the restaurant's operational characteristics (e.g., `chills_food`, `cooks_food`, `handles_raw_fish`).
- **Condition Values** – the actual state of each condition for a specific business profile, along with when and how it was answered.
- **Approved Safety Points** – a record of which safety points from the SFBB pack have been accepted by the restaurant (admin user), including when and by whom.

## Entities and Relationships

- **BusinessProfile**
  - Purpose: Stores information about a restaurant (name, site).
  - Relationships: One‑to‑many with `ConditionValue` and `ApprovedSafetyPoint`.

- **Condition**
  - Purpose: Defines the possible condition flags (ontology).
  - Relationships: One‑to‑many with `ConditionValue`.

- **ConditionValue**
  - Purpose: Stores the current value of a condition for a given business profile.
  - Relationships: Belongs to one `BusinessProfile` and one `Condition`.

- **ApprovedSafetyPoint**
  - Purpose: Records that a specific safety point has been approved by the restaurant.
  - Relationships: Belongs to one `BusinessProfile` and references an admin user (from the `users` table).

## Assumptions

- A business profile is created when a restaurant first starts the onboarding process.
- The `Condition` table is static – it is seeded from the ontology and only rarely changes.
- Only admin users can approve safety points.
- At this stage, the system does not store history of condition value changes (only the current state).
- The compiled SFBB content (sections, safe methods, safety points) is not stored in the database in v1 but it is loaded from a JSON file.

