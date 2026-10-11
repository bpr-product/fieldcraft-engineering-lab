from fieldcraft.services.etl import DocumentPipeline
from fieldcraft.services.supplier import SupplierBridge
from fieldcraft.services.measurement import MeasurementFlow


def test_document_idempotency_and_lineage(db):
    svc = DocumentPipeline(db)
    first = svc.refresh('north-demo')
    assert first['created'] == 2
    second = svc.refresh('north-demo')
    assert second['unchanged'] == 2
    docs = svc.list_documents('north-demo')
    cedar = next(d for d in docs if d['project_id']=='prj-cedar')
    assert cedar['version'] == 1
    assert 'financial:fin-1' in cedar['sources']
    assert 'Westwind' not in cedar['text']
    SupplierBridge(db).import_materials('north-demo', 'vendor-main', ['SHINGLE-01'])
    changed = svc.refresh('north-demo')
    assert changed['updated'] == 2
    new_cedar = next(d for d in svc.list_documents('north-demo') if d['project_id']=='prj-cedar')
    assert new_cedar['version'] == 2 and 'Architectural shingles' in new_cedar['text']
    MeasurementFlow(db).request('north-demo','prj-cedar')
    next_refresh = svc.refresh('north-demo')
    assert next_refresh['updated'] == 1 and next_refresh['unchanged'] == 1


def test_other_workspace_never_included(db):
    docs = DocumentPipeline(db)
    docs.refresh('north-demo')
    assert all(d['project_id']!='prj-pine' for d in docs.list_documents('north-demo'))
    assert docs.list_documents('west-demo') == []
