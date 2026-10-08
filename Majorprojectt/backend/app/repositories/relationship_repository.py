from typing import List, Optional
from app.core.data_loader import data_loader
from app.models.evidence import CrossSourceLink

class RelationshipRepository:
    def get_cross_source_links(self) -> List[CrossSourceLink]:
        raw = data_loader.load_json("relationships/cross_source_links.json")
        return [CrossSourceLink(**item) for item in raw]

    def get_link_by_id(self, link_id: str) -> Optional[CrossSourceLink]:
        for link in self.get_cross_source_links():
            if link.id == link_id:
                return link
        return None

relationship_repository = RelationshipRepository()
