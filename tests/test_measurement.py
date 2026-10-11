import pytest
from fieldcraft.services.measurement import MeasurementFlow
from fieldcraft.services.common import ConflictError, NotFoundError, ValidationError


def test_order_and_ingest_state_machine(db):
    svc = MeasurementFlow(db)
    order = svc.request('north-demo', 'prj-cedar')
    svc.move_status('north-demo', order['id'], 'processing')
    report = svc.ingest('north-demo', order['id'], {
        'roof_area_sqft': 2200, 'roof_pitch_ratio': 0.5, 'facet_count': 6})
    assert report['status'] == 'completed' and report['report']['facet_count'] == 6
    with pytest.raises(ConflictError):
        svc.ingest('north-demo', order['id'], {'roof_area_sqft':2200, 'roof_pitch_ratio':0.5, 'facet_count':6})
    with pytest.raises(ConflictError):
        svc.move_status('north-demo', order['id'], 'cancelled')


def test_invalid_report_and_tenant_scope(db):
    svc = MeasurementFlow(db)
    with pytest.raises(NotFoundError):
        svc.request('north-demo', 'prj-pine')
    order = svc.request('north-demo','prj-orion')
    with pytest.raises(ValidationError):
        svc.ingest('north-demo', order['id'], {'roof_area_sqft': -5,'roof_pitch_ratio': 0.2,'facet_count':2})
    with pytest.raises(NotFoundError):
        svc.ingest('west-demo', order['id'], {'roof_area_sqft':200,'roof_pitch_ratio':0.2,'facet_count':2})
    assert svc.list_orders('west-demo') == []
