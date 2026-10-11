import pytest
from fieldcraft.services.etl import DocumentPipeline
from fieldcraft.ai.assistant import ContextPilot
from fieldcraft.services.common import NotFoundError


def test_cost_routing_and_project_context(db):
    DocumentPipeline(db).refresh('north-demo')
    pilot = ContextPilot(db)
    result = pilot.ask('north-demo', 'demo', 'test-session', 'Why did Cedar Residence exceed material cost?')
    assert result['mode']=='structured'
    assert 'Cedar Residence' in result['answer'] and '+2,250.00' in result['answer']
    assert result['evidence'][0]['document_id']=='doc-prj-cedar'
    assert any(s['step']=='structured_query' for s in result['trace'])
    followup = pilot.ask('north-demo', 'demo', 'test-session', 'What is this project?')
    assert followup['mode']=='evidence_only'
    assert followup['evidence'][0]['project_id']=='prj-cedar'


def test_tenant_isolation_and_session_ownership(db):
    DocumentPipeline(db).refresh('north-demo')
    pilot=ContextPilot(db)
    pilot.ask('north-demo','u','scope-session','Tell me about Cedar Residence')
    with pytest.raises(NotFoundError):
        pilot.ask('west-demo','u','scope-session','Tell me about this project')
    with pytest.raises(NotFoundError):
        pilot.ask('north-demo','u','s2','Tell me about Pine Annex',active_project_id='prj-pine')
    result=pilot.ask('north-demo','u','fresh-session','What is unrelated?')
    assert result['mode']=='abstained'


def test_model_failure_never_masquerades_as_success(db):
    DocumentPipeline(db).refresh('north-demo')
    class FailingModel:
        configured=True
        def compose(self, *args): raise ConnectionError('service down')
    pilot = ContextPilot(db, model=FailingModel())
    result=pilot.ask('north-demo','u','failure-session','Tell me about Cedar Residence')
    assert result['mode']=='model_error'
    assert 'failed' in result['answer'].lower()


def test_named_project_switch_overrides_stale_selection(db):
    DocumentPipeline(db).refresh('north-demo')
    pilot=ContextPilot(db)
    pilot.ask('north-demo','u','switch-session','Tell me about Cedar Residence',active_project_id='prj-cedar')
    result=pilot.ask('north-demo','u','switch-session','Why did Orion Warehouse exceed cost?',active_project_id='prj-cedar')
    assert result['mode']=='structured'
    assert 'Orion Warehouse' in result['answer']
    assert 'Cedar Residence' not in result['answer']
    result=pilot.ask('north-demo','u','switch-session','Who won a sports event?',active_project_id='prj-cedar')
    assert result['mode']=='abstained'
    result=pilot.ask('north-demo','u','switch-session','Compare Cedar Residence and Orion Warehouse')
    assert result['mode']=='clarification'
