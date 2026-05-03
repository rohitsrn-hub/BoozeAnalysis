from typing import Dict, List
from app.db.mongo import collections

class LiquorRepository:
    async def list_all(self) -> List[Dict]:
        return await collections.liquor_data.find({}, {'_id': 0}).to_list(5000)

    async def replace_all(self, records: List[Dict]) -> int:
        await collections.liquor_data.delete_many({})
        if not records:
            return 0
        await collections.liquor_data.insert_many(records)
        return len(records)

    async def get_existing_rates(self) -> Dict[str, Dict]:
        rows = await collections.liquor_data.find({}, {'_id': 0, 'brand_name': 1, 'wholesale_rate': 1, 'selling_rate': 1, 'rate': 1}).to_list(5000)
        result = {}
        for row in rows:
            result[row['brand_name']] = {
                'wholesale_rate': row.get('wholesale_rate', 0.0),
                'selling_rate': row.get('selling_rate', row.get('rate', 0.0)),
            }
        return result

liquor_repository = LiquorRepository()
