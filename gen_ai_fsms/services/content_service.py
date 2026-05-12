# This module provides the ContentService class for loading and querying compiled SFBB content from JSON files.
# The ContentService is designed as a singleton to ensure that the JSON content is loaded only once and cached for efficient access.
# The service provides methods to retrieve all sections, safe methods by section, safety points based on condition values, and specific safety points by ID, along with their source references.

import json
import os
from typing import Dict, List, Any, Set




class ContentService:
    """Service for loading and querying compiled SFBB content from JSON."""
    
    _instance = None
    _content = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_content(self, file_path: str = "data/sfbb_chilling_cooking.json") -> Dict[str, Any]:
        """Load JSON content from file. Returns cached content on subsequent calls."""
        if self._content is None:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"SFBB content file not found: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                self._content = json.load(f)
        return self._content

    def get_all_sections(self) -> List[Dict[str, Any]]:
        """Return all sections."""
        return self.load_content().get("sections", [])

    def get_safe_methods_by_section(self, section_id: str) -> List[Dict[str, Any]]:
        """Return safe methods for a given section."""
        for section in self.get_all_sections():
            if section.get("section_id") == section_id:
                return section.get("safe_methods", [])
        return []

    def get_safety_points_by_conditions(self, condition_values: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Return all safety points whose effective condition is true.
        
        Inheritance rule:
        - If a safety point has its own condition_id, that condition must be true.
        - Otherwise, the safety point inherits the condition_id of its parent safe method.
        - The safe method's condition_id is used as the effective condition.
        
        condition_values: dict mapping condition_id -> "true"/"false"/"unknown"/"not_asked"
        """
        result = []
        content = self.load_content()
        
        for section in content.get("sections", []):
            for safe_method in section.get("safe_methods", []):
                safe_method_condition = safe_method.get("condition_id")
                for sp in safe_method.get("safety_points", []):
                    # Determine effective condition for this safety point
                    sp_condition = sp.get("condition_id")
                    effective_condition = sp_condition if sp_condition else safe_method_condition
                    
                    # Check if condition is present and true
                    if effective_condition and condition_values.get(effective_condition) == "true":
                        # Augment safety point with inherited metadata
                        enriched_sp = sp.copy()
                        if not sp_condition:
                            enriched_sp["inherited_condition"] = safe_method_condition
                        enriched_sp["section_id"] = section.get("section_id")
                        enriched_sp["section_name"] = section.get("section_name")
                        enriched_sp["safe_method_id"] = safe_method.get("safe_method_id")
                        enriched_sp["safe_method_name"] = safe_method.get("safe_method_name")
                        result.append(enriched_sp)
        return result

    def get_safety_point_by_id(self, safety_point_id: str) -> Dict[str, Any] | None:
        """Return a single safety point by its ID."""
        content = self.load_content()
        for section in content.get("sections", []):
            for safe_method in section.get("safe_methods", []):
                for sp in safe_method.get("safety_points", []):
                    if sp.get("safety_point_id") == safety_point_id:
                        # Enrich with parent metadata
                        enriched = sp.copy()
                        enriched["section_id"] = section.get("section_id")
                        enriched["section_name"] = section.get("section_name")
                        enriched["safe_method_id"] = safe_method.get("safe_method_id")
                        enriched["safe_method_name"] = safe_method.get("safe_method_name")
                        return enriched
        return None

    def get_source_references(self, safety_point_id: str) -> List[str]:
        """Return source references for a safety point."""
        sp = self.get_safety_point_by_id(safety_point_id)
        return sp.get("source_references", []) if sp else []
