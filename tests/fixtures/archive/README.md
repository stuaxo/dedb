# Captured archive.org responses

Real API responses, captured once and replayed in `tests/test_archive.py`
and `tests/test_cli_archive.py` so the archive backend is tested against
the actual shape of archive.org data without hitting the network.

| file | source |
|------|--------|
| `item_electro_man_1992.json` | `internetarchive.get_item("msdos_Electro_Man_1992").item_metadata` — a single-`.zip` DOSBox item |
| `search_favorites.json` | first 5 docs of `search_items("collection:softwarelibrary_msdos_games", fields=["identifier","title","year"], sorts=["titleSorter asc"])` — same doc shape the favorites query returns |

To refresh:

```python
import json
from internetarchive import get_item, search_items

json.dump(get_item("msdos_Electro_Man_1992").item_metadata,
          open("item_electro_man_1992.json", "w"), indent=1, sort_keys=True)

docs = list(search_items("collection:softwarelibrary_msdos_games",
                         fields=["identifier", "title", "year"],
                         sorts=["titleSorter asc"], params={"rows": 5, "page": 1}))
json.dump(docs[:5], open("search_favorites.json", "w"), indent=1)
```
