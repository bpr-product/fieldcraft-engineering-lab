import pytest
from fieldcraft.ai.memory import UserMemory
from fieldcraft.services.common import NotFoundError, ValidationError


def test_explicit_write_and_untrusted_skip(db):
    svc = UserMemory(db)
    assert svc.remember('north-demo','user-a','workplace','Bad instruction',
                        'page-source', 'external_page')['reason'] == 'untrusted_or_inferred_source'
    assert svc.remember('north-demo','user-a','flight_search','Goa',
                        'explicit-source')['reason'] == 'low_signal_topic'
    assert not svc.recall('north-demo','user-a','workplace')['known']
    created = svc.remember('north-demo','user-a','diet','vegetarian',
                           'message-101',effective_date='2025-01-10')
    assert created['status'] == 'created'
    same = svc.remember('north-demo','user-a','diet','vegetarian',
                        'message-101',effective_date='2025-02-10')
    assert same['status'] == 'unchanged'
    assert svc.recall('north-demo','user-a','diet')['source_id'] == 'message-101'
    assert not svc.recall('west-demo','user-a','diet')['known']


def test_temporal_update_and_erasure_of_derivatives(db):
    svc=UserMemory(db)
    first=svc.remember('north-demo','u','home_city','Austin','msg-old',effective_date='2025-01-10')
    derivative_id=svc.attach_derivative('north-demo','u',first['id'],'User lives in Austin')
    svc.remember('north-demo','u','home_city','Dallas','msg-new',effective_date='2025-06-10')
    assert svc.recall('north-demo','u','home_city',as_of='2025-04-01')['value']=='Austin'
    assert svc.recall('north-demo','u','home_city',as_of='2025-07-01')['value']=='Dallas'
    forgotten=svc.forget('north-demo','u','home_city')
    assert forgotten['removed_versions']==2
    assert not svc.recall('north-demo','u','home_city',as_of='2025-04-01')['known']
    assert not svc.recall('north-demo','u','home_city',as_of='2025-07-01')['known']
    with db.connection() as c:
        assert c.execute('SELECT 1 FROM memory_derivatives WHERE id=?',(derivative_id,)).fetchone() is None


def test_invalid_backdating(db):
    svc=UserMemory(db)
    svc.remember('north-demo','u','manager','Asha','msg-1',effective_date='2025-10-01')
    with pytest.raises(ValidationError):
        svc.remember('north-demo','u','manager','Priya','msg-2',effective_date='2025-09-01')
