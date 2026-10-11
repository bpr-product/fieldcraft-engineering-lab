import pytest
from fieldcraft.services.supplier import SupplierBridge
from fieldcraft.services.common import NotFoundError


def test_import_validates_every_item_and_duplicate(db):
    svc = SupplierBridge(db)
    result = svc.import_materials('north-demo', 'vendor-main', [
        'SHINGLE-01','NOPRICE-05','UNKNOWN-04','SHINGLE-01','NOT-A-SKU','FLASH-02'])
    assert result['added'] == 2 and result['skipped'] == 4
    rows = {x['sku']:x for x in result['items'] if x['sku'] not in ('SHINGLE-01',)}
    assert rows['NOPRICE-05']['reason'] == 'missing_price'
    assert rows['UNKNOWN-04']['reason'] == 'unmapped_uom'
    assert rows['NOT-A-SKU']['reason'] == 'unknown_item'
    assert result['items'][3]['reason'] == 'duplicate_in_request'
    repeat = svc.import_materials('north-demo', 'vendor-main', ['SHINGLE-01'])
    assert repeat['items'][0]['reason'] == 'already_imported'
    materials = svc.list_materials('north-demo')
    assert len(materials) == 2
    assert materials[0]['uom'] in ('bundle','linear_foot')


def test_branch_availability_and_workspace_policy(db):
    svc = SupplierBridge(db)
    result = svc.import_materials('north-demo', 'vendor-main', ['FLASH-02'], 'branch-b')
    assert result['items'][0]['reason'] == 'not_available_to_order'
    with pytest.raises(NotFoundError):
        svc.import_materials('west-demo', 'vendor-main', ['SHINGLE-01'])
    result = svc.import_materials('west-demo', 'vendor-west', ['SHINGLE-01'])
    assert result['items'][0]['reason'] == 'uom_not_enabled_for_workspace'
    assert svc.list_materials('west-demo') == []
