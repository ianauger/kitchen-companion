"""Tests for store CRUD, aisle classification, and override persistence."""
import pytest
import json
from app.models import Store, StoreAisle, AisleOverride, ShoppingItem
from app import db
from app.auth import User


# ── Store CRUD ───────────────────────────────────────────────────────────

def test_get_stores_empty(client):
    """GET /stores returns empty list initially."""
    resp = client.get('/stores')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data == []


def test_create_store_returns_with_15_aisles(auth_client, app):
    """POST /stores creates a store with default 15 aisles."""
    resp = auth_client.post('/stores',
                            json={'name': 'Safeway'})
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data['name'] == 'Safeway'
    assert data['aisle_count'] == 15
    assert 'aisles' in data
    assert len(data['aisles']) == 15


def test_store_aisle_order_produce_first_other_last(auth_client, app):
    """Store aisles start with Produce and end with Other."""
    resp = auth_client.post('/stores',
                            json={'name': 'Safeway'})
    data = json.loads(resp.data)
    aisles = data['aisles']
    assert aisles[0]['name'] == 'Produce'
    assert aisles[0]['sort_order'] == 0
    assert aisles[-1]['name'] == 'Other'
    assert aisles[-1]['sort_order'] == 14


def test_second_store_also_gets_15_default_aisles(auth_client, app):
    """Creating a second store also seeds 15 default aisles."""
    auth_client.post('/stores', json={'name': 'Store A'})
    resp = auth_client.post('/stores', json={'name': 'Store B'})
    data = json.loads(resp.data)
    assert data['name'] == 'Store B'
    assert len(data['aisles']) == 15


def test_renaming_store_updates_name(auth_client, app):
    """PUT /stores/<id> renames a store."""
    r = auth_client.post('/stores', json={'name': 'Old Name'})
    store_id = json.loads(r.data)['id']

    resp = auth_client.put(f'/stores/{store_id}',
                           json={'name': 'New Name'})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['name'] == 'New Name'
    assert data['id'] == store_id


def test_reorder_store_aisles_persists(auth_client, app):
    """PUT /stores/<id>/aisles persists new aisle order."""
    r = auth_client.post('/stores', json={'name': 'Test Store'})
    store_data = json.loads(r.data)
    store_id = store_data['id']
    aisles = store_data['aisles']

    # Swap first two aisles
    aisles[0]['sort_order'], aisles[1]['sort_order'] = 1, 0

    resp = auth_client.put(f'/stores/{store_id}/aisles',
                           json={'aisles': aisles})
    assert resp.status_code == 200
    updated = json.loads(resp.data)
    updated_aisles = updated['aisles']
    # First aisle should now be what was originally second
    assert updated_aisles[0]['name'] == aisles[1]['name']
    assert updated_aisles[0]['sort_order'] == 0
    assert updated_aisles[1]['name'] == aisles[0]['name']
    assert updated_aisles[1]['sort_order'] == 1


def test_rename_store_requires_name(auth_client, app):
    """Renaming a store without a name returns 400."""
    r = auth_client.post('/stores', json={'name': 'Store'})
    store_id = json.loads(r.data)['id']
    resp = auth_client.put(f'/stores/{store_id}',
                           json={'name': '   '})
    assert resp.status_code == 400


# ── Auto-Categorization (classify_aisle) ─────────────────────────────────

def test_classify_chicken_thighs_meat_seafood(app):
    """'2 lbs chicken thighs' → Meat & Seafood."""
    from app.models import classify_aisle
    assert classify_aisle('2 lbs chicken thighs') == 'Meat & Seafood'


def test_classify_spinach_produce(app):
    """'fresh spinach' → Produce."""
    from app.models import classify_aisle
    assert classify_aisle('fresh spinach') == 'Produce'


def test_classify_milk_dairy(app):
    """'whole milk' → Dairy."""
    from app.models import classify_aisle
    assert classify_aisle('whole milk') == 'Dairy'


def test_classify_bread_bakery(app):
    """'sourdough bread' → Bakery."""
    from app.models import classify_aisle
    assert classify_aisle('sourdough bread') == 'Bakery'


def test_classify_unknown_other(app):
    """Unrecognized item → Other."""
    from app.models import classify_aisle
    assert classify_aisle('unrecognized item xyz') == 'Other'


def test_classify_empty_string_other(app):
    """Empty string → Other."""
    from app.models import classify_aisle
    assert classify_aisle('') == 'Other'


def test_add_item_auto_assigned_correct_aisle(auth_client, app):
    """POST /shopping-items auto-classifies aisle for new item."""
    # First create a store with default aisles
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_data = json.loads(r.data)

    resp = auth_client.post('/shopping-items',
                            json={
                                'items': [
                                    {'name': '2 lbs chicken thighs', 'recipe_id': None}
                                ],
                                'store_id': store_data['id']
                            })
    assert resp.status_code == 201
    items = json.loads(resp.data)['items']
    assert len(items) == 1
    assert items[0]['aisle_name'] == 'Meat & Seafood'


# ── Override Persistence ─────────────────────────────────────────────────

def test_changing_aisle_creates_override(auth_client, app):
    """After changing an item's aisle, an override is created."""
    # Create store
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_data = json.loads(r.data)
    store_id = store_data['id']

    # Find "Meat & Seafood" and "Produce" aisle IDs
    produce_aisle = next(a for a in store_data['aisles'] if a['name'] == 'Produce')

    # Add an item that auto-classifies to "Meat & Seafood"
    resp = auth_client.post('/shopping-items',
                            json={
                                'items': [
                                    {'name': 'chicken breast', 'recipe_id': None}
                                ],
                                'store_id': store_id
                            })
    item = json.loads(resp.data)['items'][0]

    # Change its aisle to Produce (which differs from auto-classified "Meat & Seafood")
    resp = auth_client.put(f'/shopping-items/{item["id"]}',
                           json={
                               'aisle_id': produce_aisle['id'],
                               'store_id': store_id
                           })
    assert resp.status_code == 200

    # Verify override exists
    with app.app_context():
        override = AisleOverride.query.filter_by(
            store_id=store_id,
            item_name_normalized='chicken breast'
        ).first()
        assert override is not None
        assert override.aisle_id == produce_aisle['id']


def test_adding_same_item_uses_override(auth_client, app):
    """Adding the same item name again uses the override instead of keyword match."""
    # Create store
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_data = json.loads(r.data)
    store_id = store_data['id']

    # Find "Produce" aisle (where bread would NOT normally go)
    produce_aisle = next(a for a in store_data['aisles'] if a['name'] == 'Produce')

    # Add "sourdough bread" and manually override to Produce
    resp = auth_client.post('/shopping-items',
                            json={
                                'items': [
                                    {'name': 'sourdough bread', 'recipe_id': None}
                                ],
                                'store_id': store_id
                            })
    item = json.loads(resp.data)['items'][0]

    # Override to Produce
    auth_client.put(f'/shopping-items/{item["id"]}',
                    json={
                        'aisle_id': produce_aisle['id'],
                        'store_id': store_id
                    })

    # Mark the first one as purchased so a new one can be added
    auth_client.put(f'/shopping-items/{item["id"]}',
                    json={'purchased': True})

    # Add again — should use override, not keyword "Bakery"
    resp2 = auth_client.post('/shopping-items',
                             json={
                                 'items': [
                                     {'name': 'sourdough bread', 'recipe_id': None}
                                 ],
                                 'store_id': store_id
                             })
    new_item = json.loads(resp2.data)['items'][0]
    assert new_item['aisle_name'] == 'Produce'


def test_get_store_overrides_returns_saved_overrides(auth_client, app):
    """GET /stores/<id>/overrides returns saved overrides."""
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_id = json.loads(r.data)['id']

    # Create an item and override via PUT
    resp = auth_client.post('/shopping-items',
                            json={
                                'items': [
                                    {'name': 'tortillas', 'recipe_id': None}
                                ],
                                'store_id': store_id
                            })
    item = json.loads(resp.data)['items'][0]
    store_data = json.loads(r.data)
    produce_aisle = next(a for a in store_data['aisles'] if a['name'] == 'Produce')
    auth_client.put(f'/shopping-items/{item["id"]}',
                    json={
                        'aisle_id': produce_aisle['id'],
                        'store_id': store_id
                    })

    # Get overrides
    resp = auth_client.get(f'/stores/{store_id}/overrides')
    assert resp.status_code == 200
    overrides = json.loads(resp.data)
    assert len(overrides) >= 1
    assert any(o['item_name_normalized'] == 'tortillas' for o in overrides)


def test_import_overrides_from_json(auth_client, app):
    """POST /stores/<id>/overrides imports overrides from JSON."""
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_id = json.loads(r.data)['id']

    resp = auth_client.post(f'/stores/{store_id}/overrides',
                            json={
                                'overrides': [
                                    {'item_name_normalized': 'sriracha', 'aisle_name': 'Condiments & Sauces'},
                                    {'item_name_normalized': 'gochujang', 'aisle_name': 'Condiments & Sauces'},
                                ]
                            })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['created'] == 2
    assert data['updated'] == 0

    # Verify overrides exist
    resp2 = auth_client.get(f'/stores/{store_id}/overrides')
    overrides = json.loads(resp2.data)
    names = [o['item_name_normalized'] for o in overrides]
    assert 'sriracha' in names
    assert 'gochujang' in names


def test_override_scoped_to_store(auth_client, app):
    """Override in store A doesn't affect store B."""
    # Create two stores
    r_a = auth_client.post('/stores', json={'name': 'Store A'})
    store_a_id = json.loads(r_a.data)['id']
    r_b = auth_client.post('/stores', json={'name': 'Store B'})
    store_b_id = json.loads(r_b.data)['id']

    # Get Produce aisle for store A
    produce_a = next(a for a in json.loads(r_a.data)['aisles'] if a['name'] == 'Produce')

    # Add "tortillas" to store A and override to Produce
    resp = auth_client.post('/shopping-items',
                            json={
                                'items': [
                                    {'name': 'tortillas', 'recipe_id': None}
                                ],
                                'store_id': store_a_id
                            })
    item = json.loads(resp.data)['items'][0]
    auth_client.put(f'/shopping-items/{item["id"]}',
                    json={
                        'aisle_id': produce_a['id'],
                        'store_id': store_a_id
                    })

    # Get overrides for store A — should have tortillas→Produce
    resp_a_overrides = auth_client.get(f'/stores/{store_a_id}/overrides')
    overrides_a = json.loads(resp_a_overrides.data)
    assert any(o['item_name_normalized'] == 'tortillas' for o in overrides_a)

    # Get overrides for store B — should NOT have tortillas override
    resp_b_overrides = auth_client.get(f'/stores/{store_b_id}/overrides')
    overrides_b = json.loads(resp_b_overrides.data)
    assert not any(o['item_name_normalized'] == 'tortillas' for o in overrides_b)


# ── Grouped Response ─────────────────────────────────────────────────────

def test_get_shopping_items_grouped_by_aisle(auth_client, app):
    """GET /shopping-items?store_id=X returns items grouped by aisle in correct order."""
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_data = json.loads(r.data)
    store_id = store_data['id']

    # Add items from different categories
    auth_client.post('/shopping-items',
                     json={
                         'items': [
                             {'name': 'spinach', 'recipe_id': None},
                             {'name': 'chicken breast', 'recipe_id': None},
                             {'name': 'milk', 'recipe_id': None},
                         ],
                         'store_id': store_id
                     })

    resp = auth_client.get(f'/shopping-items?store_id={store_id}')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'aisles' in data
    assert 'store' in data

    aisles_with_items = data['aisles']
    # Should have at least 3 groups (Produce, Meat & Seafood, Dairy)
    aisle_names = [a['name'] for a in aisles_with_items]
    assert 'Produce' in aisle_names
    assert 'Meat & Seafood' in aisle_names
    assert 'Dairy' in aisle_names

    # Produce should come before Meat & Seafood (aisle order from defaults)
    produce_idx = aisle_names.index('Produce')
    meat_idx = aisle_names.index('Meat & Seafood')
    dairy_idx = aisle_names.index('Dairy')
    assert produce_idx < meat_idx < dairy_idx


def test_item_no_matching_aisle_goes_to_other(auth_client, app):
    """Items with no matching aisle go to Other at the end."""
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_id = json.loads(r.data)['id']

    auth_client.post('/shopping-items',
                     json={
                         'items': [
                             {'name': 'xyzzy flibble widget', 'recipe_id': None},
                         ],
                         'store_id': store_id
                     })

    resp = auth_client.get(f'/shopping-items?store_id={store_id}')
    data = json.loads(resp.data)
    aisles = data['aisles']

    # The last group should be "Other" with our unknown item
    assert aisles[-1]['name'] == 'Other'
    assert len(aisles[-1]['items']) >= 1
    assert aisles[-1]['items'][0]['aisle_name'] == 'Other'


def test_get_aisles_endpoint_returns_ordered_aisles(auth_client, app):
    """GET /aisles?store_id=X returns aisles ordered by sort_order."""
    r = auth_client.post('/stores', json={'name': 'My Store'})
    store_id = json.loads(r.data)['id']

    resp = auth_client.get(f'/aisles?store_id={store_id}')
    assert resp.status_code == 200
    aisles = json.loads(resp.data)
    assert len(aisles) == 15
    assert aisles[0]['name'] == 'Produce'
    assert aisles[-1]['name'] == 'Other'
    # sort_order should be sequential
    for i, a in enumerate(aisles):
        assert a['sort_order'] == i
