import asyncio
from types import SimpleNamespace


def test_jev_selects_registered_candidate_and_accumulates_real_usage():
    from hermes_cua_with_jev.jev import Jev

    class Client:
        async def system_one(self, **kwargs):
            assert kwargs['questions']['action'].criteria['c0']['label'] == 'Save'
            assert 'stop' in kwargs['questions']['action'].criteria
            return SimpleNamespace(choices={'action': SimpleNamespace(choice='c0')},
                                   usage=SimpleNamespace(input_tokens=331, output_tokens=31), model='jev-test')

    selector = Jev(Client())
    result = asyncio.run(selector.choose('Save the document', [{'role':'button','label':'Save'}],
                         [{'id':'c0','operation':'click','role':'button','label':'Save','input':None}]))
    assert result == 'c0'
    assert selector.usage == {'input_tokens':331, 'output_tokens':31, 'calls':1}
    assert selector.model == 'jev-test'


def test_missing_usage_is_not_reported_as_zero():
    from hermes_cua_with_jev.jev import Jev
    class Client:
        async def system_one(self, **kwargs):
            return SimpleNamespace(choices={'action':SimpleNamespace(choice='stop')},
                    usage=SimpleNamespace(input_tokens=None,output_tokens=None), model='test')
    selector = Jev(Client())
    assert asyncio.run(selector.choose('goal', [], [])) == 'stop'
    assert selector.usage == {'input_tokens':None,'output_tokens':None,'calls':1}
