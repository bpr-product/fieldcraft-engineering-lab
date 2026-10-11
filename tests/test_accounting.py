import pytest
from fieldcraft.services.accounting import AccountingBridge, PROVIDER
from fieldcraft.services.common import NotFoundError
from fieldcraft.database import utc_now


def test_sync_idempotent_and_remote_change_conflict(db):
    svc = AccountingBridge(db)
    first = svc.sync('north-demo')
    assert first['created'] == 3 and first['conflicts'] == 0
    again = svc.sync('north-demo')
    assert again['created'] == 0 and again['unchanged'] == 3
    mappings = svc.mappings('north-demo')
    assert len(mappings) == 3 and len({r['remote_id'] for r in mappings}) == 3
    with db.connection() as c:
        c.execute('UPDATE financial_records SET amount_cents=?,updated_at=? WHERE id=? AND tenant_id=?',
                  (55000, utc_now(), 'fin-1', 'north-demo'))
    update = svc.push_one('north-demo', 'fin-1')
    assert update['status'] == 'updated' and update['version'] == 2
    svc.simulate_remote_change('north-demo', 'fin-1', 60000)
    result = svc.sync('north-demo')
    assert result['conflicts'] == 1
    assert next(r for r in result['records'] if r['record_id'] == 'fin-1')['status'] == 'conflict'


def test_import_existing_remote_is_idempotent(db):
    svc = AccountingBridge(db)
    with db.connection() as c:
        c.execute('''INSERT INTO remote_accounting_records
            (remote_id,tenant_id,external_key,project_id,kind,amount_cents,description,remote_version)
            VALUES ('ext-one','north-demo','other-external-1','prj-cedar','expense',12000,'Sample note',1)''')
    first = svc.import_external('north-demo', 'ext-one')
    assert first['status'] == 'created'
    second = svc.import_external('north-demo', 'ext-one')
    assert second == {'status': 'already_imported', 'record_id': first['record_id']}


def test_finance_workspace_isolation(db):
    svc = AccountingBridge(db)
    with pytest.raises(NotFoundError):
        svc.push_one('north-demo', 'fin-4')
    with pytest.raises(NotFoundError):
        svc.import_external('west-demo', 'missing')
    svc.sync('north-demo')
    assert all(x['local_id'] != 'fin-4' for x in svc.mappings('north-demo'))
