import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gen_ai_fsms.db.models.condition import Condition

load_dotenv(".env.test", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def seed():
    session = Session()
    
    conditions = [
        {"condition_id": "chills_food", "condition_name": "Chills Food", "description": "Restaurant keeps any food chilled in fridges or display units"},
        {"condition_id": "displays_chilled_food", "condition_name": "Displays Chilled Food", "description": "Restaurant displays chilled food for customers (buffet, self-service)"},
        {"condition_id": "chills_hot_food", "condition_name": "Chills Hot Food", "description": "Restaurant cools hot cooked food for later use"},
        {"condition_id": "defrosts_food", "condition_name": "Defrosts Food", "description": "Restaurant defrosts frozen food before use"},
        {"condition_id": "uses_sink_to_defrost_food", "condition_name": "Uses Sink to Defrost", "description": "Restaurant uses a sink to defrost food"},
        {"condition_id": "freezes_food", "condition_name": "Freezes Food", "description": "Restaurant freezes food on site or stores food in freezers"},
        {"condition_id": "buys_frozen_food", "condition_name": "Buys Frozen Food", "description": "Restaurant buys food that arrives frozen"},
        {"condition_id": "stores_food_that_must_be_kept_frozen", "condition_name": "Stores Must-Keep-Frozen Food", "description": "Restaurant stores food that must remain frozen (e.g., ice cream)"},
        {"condition_id": "cooks_food", "condition_name": "Cooks or Prepares Food", "description": "Restaurant prepares or cooks food on site"},
        {"condition_id": "reheats_food", "condition_name": "Reheats Food", "description": "Restaurant reheats previously cooked food"},
        {"condition_id": "uses_microwave_reheating", "condition_name": "Uses Microwave for Reheating", "description": "Restaurant uses a microwave to reheat food"},
        {"condition_id": "hot_holds_food", "condition_name": "Hot Holds Food", "description": "Restaurant keeps food hot before serving"},
        {"condition_id": "displays_hot_food", "condition_name": "Displays Hot Food", "description": "Restaurant displays hot food (buffet, service counter)"},
        {"condition_id": "delivers_food", "condition_name": "Delivers Food", "description": "Restaurant delivers food to customers or offers collection"},
        {"condition_id": "handles_ready_to_eat_food", "condition_name": "Handles Ready-to-Eat Food", "description": "Restaurant prepares ready-to-eat food (salads, sandwiches, cooked foods served cold)"},
        {"condition_id": "uses_slicer", "condition_name": "Uses Slicer", "description": "Restaurant uses a slicer for cooked meat or ready-to-eat food"},
        {"condition_id": "handles_raw_meat_or_poultry", "condition_name": "Handles Raw Meat or Poultry", "description": "Restaurant handles raw meat or poultry"},
        {"condition_id": "cooks_rice", "condition_name": "Cooks Rice", "description": "Restaurant cooks rice"},
        {"condition_id": "handles_eggs", "condition_name": "Handles Eggs", "description": "Restaurant uses eggs or makes foods containing eggs"},
        {"condition_id": "cooks_dried_pulses", "condition_name": "Cooks Dried Pulses", "description": "Restaurant cooks dried pulses such as dried beans"},
        {"condition_id": "handles_raw_fish", "condition_name": "Handles Raw Fish", "description": "Restaurant cooks or handles raw fish"},
        {"condition_id": "handles_raw_molluscs_or_crustaceans", "condition_name": "Handles Raw Molluscs or Crustaceans", "description": "Restaurant handles raw shellfish (prawns, mussels, crab, lobster)"},
        {"condition_id": "handles_bread_bakery_or_potatoes", "condition_name": "Handles Bread, Bakery or Potatoes", "description": "Restaurant handles bread, bakery products, chips, fries or similar potato products"},
    ]
    
    for cond_data in conditions:
        existing = session.query(Condition).filter_by(condition_id=cond_data["condition_id"]).first()
        if not existing:
            condition = Condition(
                condition_id=cond_data["condition_id"],
                condition_name=cond_data["condition_name"],
                description=cond_data["description"],
                status="active"
            )
            session.add(condition)
    
    session.commit()
    print(f"Seeded/verified {len(conditions)} conditions.")
    session.close()

if __name__ == "__main__":
    seed()
