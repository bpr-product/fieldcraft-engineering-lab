from fastapi.testclient import TestClient
from fieldcraft.api import create_app


def test_api_app_workflow(db):
    with TestClient(create_app(db)) as client:
        overview = client.get('/api/overview').json()
        assert overview['project_count']==2
        assert overview['providers']=='synthetic_only'
        assert client.post('/api/accounting/sync',json={'tenant_id':'north-demo'}).status_code==200
        docs = client.post('/api/documents/refresh',json={'tenant_id':'north-demo'}).json()
        assert docs['created']==2
        answer = client.post('/api/assistant/ask',json={'tenant_id':'north-demo',
            'question':'Why did Cedar Residence exceed material cost?'}).json()
        assert answer['mode']=='structured'
        bad = client.post('/api/supplier/import',json={
            'tenant_id':'west-demo','vendor_id':'vendor-main','skus':['SHINGLE-01']})
        assert bad.status_code==404
        page = client.get('/')
        assert page.status_code==200 and 'FieldCraft' in page.text
